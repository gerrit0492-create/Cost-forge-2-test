"""Tests for utils: pricing, validators, market, quotes, presets, routing, history."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# utils.pricing
# ---------------------------------------------------------------------------

class TestComputeCosts:
    def _make_frames(self, mass=2.0, price=5.0, runtime=1.0, machine=10.0, labor=5.0, overhead=0.10, margin=0.20):
        mats = pd.DataFrame({"material_id": ["M1"], "price_eur_per_kg": [price]})
        procs = pd.DataFrame({
            "process_id": ["P1"],
            "machine_rate_eur_h": [machine],
            "labor_rate_eur_h": [labor],
            "overhead_pct": [overhead],
            "margin_pct": [margin],
        })
        bom = pd.DataFrame({
            "line_id": ["L1"],
            "material_id": ["M1"],
            "process_route": ["P1"],
            "mass_kg": [mass],
            "runtime_h": [runtime],
        })
        return mats, procs, bom

    def test_basic_calculation(self):
        from utils.pricing import compute_costs
        mats, procs, bom = self._make_frames(mass=2.0, price=5.0, runtime=1.0, machine=10.0, labor=5.0, overhead=0.10, margin=0.20)
        df = compute_costs(mats, procs, bom)
        assert len(df) == 1
        row = df.iloc[0]
        assert row["material_cost"] == pytest.approx(10.0)   # 2 * 5
        assert row["process_cost"] == pytest.approx(15.0)    # 1 * (10+5)
        assert row["overhead"] == pytest.approx(2.5)         # (10+15) * 0.10
        assert row["base_cost"] == pytest.approx(27.5)       # 10+15+2.5
        assert row["margin"] == pytest.approx(5.5)           # 27.5 * 0.20
        assert row["total_cost"] == pytest.approx(33.0)      # 27.5+5.5

    def test_zero_overhead_zero_margin(self):
        from utils.pricing import compute_costs
        mats, procs, bom = self._make_frames(overhead=0.0, margin=0.0)
        df = compute_costs(mats, procs, bom)
        row = df.iloc[0]
        assert row["overhead"] == pytest.approx(0.0)
        assert row["margin"] == pytest.approx(0.0)
        assert row["total_cost"] == pytest.approx(row["base_cost"])

    def test_missing_required_column_raises(self):
        from utils.pricing import compute_costs
        mats = pd.DataFrame({"material_id": ["M1"], "price_eur_per_kg": [5.0]})
        procs = pd.DataFrame({"process_id": ["P1"], "machine_rate_eur_h": [10.0]})  # missing cols
        bom = pd.DataFrame({"material_id": ["M1"], "process_route": ["P1"], "mass_kg": [1.0], "runtime_h": [1.0]})
        with pytest.raises(ValueError, match="Ontbrekende kolommen"):
            compute_costs(mats, procs, bom)

    def test_multiple_rows(self):
        from utils.pricing import compute_costs
        mats = pd.DataFrame({"material_id": ["M1", "M2"], "price_eur_per_kg": [5.0, 10.0]})
        procs = pd.DataFrame({
            "process_id": ["P1"],
            "machine_rate_eur_h": [10.0],
            "labor_rate_eur_h": [5.0],
            "overhead_pct": [0.0],
            "margin_pct": [0.0],
        })
        bom = pd.DataFrame({
            "material_id": ["M1", "M2"],
            "process_route": ["P1", "P1"],
            "mass_kg": [1.0, 2.0],
            "runtime_h": [1.0, 1.0],
        })
        df = compute_costs(mats, procs, bom)
        assert len(df) == 2
        assert df["total_cost"].iloc[0] == pytest.approx(20.0)   # 1*5 + 1*15
        assert df["total_cost"].iloc[1] == pytest.approx(35.0)   # 2*10 + 1*15


# ---------------------------------------------------------------------------
# utils.validators
# ---------------------------------------------------------------------------

class TestCheckMissing:
    def test_all_present(self):
        from utils.validators import check_missing
        df = pd.DataFrame({"a": [1], "b": [2]})
        assert check_missing(df, ["a", "b"]) == []

    def test_some_missing(self):
        from utils.validators import check_missing
        df = pd.DataFrame({"a": [1]})
        missing = check_missing(df, ["a", "b", "c"])
        assert "b" in missing and "c" in missing

    def test_empty_required(self):
        from utils.validators import check_missing
        df = pd.DataFrame({"a": [1]})
        assert check_missing(df, []) == []


class TestCheckPositive:
    def test_all_positive(self):
        from utils.validators import check_positive
        df = pd.DataFrame({"price": [1.0, 2.0], "qty": [3, 4]})
        assert check_positive(df, ["price", "qty"]) == []

    def test_zero_is_bad(self):
        from utils.validators import check_positive
        df = pd.DataFrame({"price": [0.0, 1.0]})
        assert "price" in check_positive(df, ["price"])

    def test_negative_is_bad(self):
        from utils.validators import check_positive
        df = pd.DataFrame({"price": [-1.0, 2.0]})
        assert "price" in check_positive(df, ["price"])

    def test_missing_column_skipped(self):
        from utils.validators import check_positive
        df = pd.DataFrame({"a": [1.0]})
        assert check_positive(df, ["nonexistent"]) == []


class TestWithin:
    def test_within_range(self):
        from utils.validators import within
        df = pd.DataFrame({"x": [0.5, 0.9]})
        assert within(df, "x", 0.0, 1.0) is True

    def test_below_lo(self):
        from utils.validators import within
        df = pd.DataFrame({"x": [-0.1, 0.5]})
        assert within(df, "x", 0.0, 1.0) is False

    def test_above_hi(self):
        from utils.validators import within
        df = pd.DataFrame({"x": [0.5, 1.1]})
        assert within(df, "x", 0.0, 1.0) is False

    def test_no_bounds(self):
        from utils.validators import within
        df = pd.DataFrame({"x": [-999.0, 999.0]})
        assert within(df, "x", None, None) is True

    def test_missing_column_returns_false(self):
        from utils.validators import within
        df = pd.DataFrame({"a": [1.0]})
        assert within(df, "nonexistent", 0.0, 1.0) is False


class TestBusinessRules:
    def _make_valid(self):
        mats = pd.DataFrame({"price_eur_per_kg": [5.0]})
        procs = pd.DataFrame({
            "machine_rate_eur_h": [10.0],
            "labor_rate_eur_h": [5.0],
            "overhead_pct": [0.10],
            "margin_pct": [0.20],
        })
        bom = pd.DataFrame({"qty": [2], "mass_kg": [1.0], "runtime_h": [0.5]})
        return mats, procs, bom

    def test_all_valid(self):
        from utils.validators import business_rules, all_rules_ok
        mats, procs, bom = self._make_valid()
        rules = business_rules(mats, procs, bom)
        assert all_rules_ok(rules)

    def test_negative_rate_fails(self):
        from utils.validators import business_rules, all_rules_ok
        mats, procs, bom = self._make_valid()
        procs["machine_rate_eur_h"] = -1.0
        rules = business_rules(mats, procs, bom)
        assert not all_rules_ok(rules)
        names = {r.name for r in rules if not r.ok}
        assert "rates_positive" in names

    def test_overhead_out_of_range_fails(self):
        from utils.validators import business_rules, all_rules_ok
        mats, procs, bom = self._make_valid()
        procs["overhead_pct"] = 1.5
        rules = business_rules(mats, procs, bom)
        assert not all_rules_ok(rules)

    def test_zero_qty_fails(self):
        from utils.validators import business_rules, all_rules_ok
        mats, procs, bom = self._make_valid()
        bom["qty"] = 0
        rules = business_rules(mats, procs, bom)
        assert not all_rules_ok(rules)


class TestSummarizeRules:
    def test_ok_prefix(self):
        from utils.validators import Rule, summarize_rules
        rules = [Rule("r1", True, "all good"), Rule("r2", False, "bad")]
        s = summarize_rules(rules)
        assert "✅" in s
        assert "❌" in s

    def test_empty(self):
        from utils.validators import summarize_rules
        assert summarize_rules([]) == ""


# ---------------------------------------------------------------------------
# utils.market
# ---------------------------------------------------------------------------

class TestLoadMarketCsv:
    def test_missing_file_returns_empty(self):
        from utils.market import load_market_csv
        df = load_market_csv("/nonexistent/path.csv")
        assert list(df.columns) == ["series", "date", "value"]
        assert len(df) == 0

    def test_loads_valid_csv(self, tmp_path):
        from utils.market import load_market_csv
        p = tmp_path / "mkt.csv"
        p.write_text("series,date,value\nSteel,2024-01,100\n")
        df = load_market_csv(p)
        assert len(df) == 1
        assert df["series"].iloc[0] == "Steel"


class TestYoyChange:
    def _make_df(self, values):
        rows = [{"series": "Steel", "date": f"2023-{i+1:02d}", "value": v} for i, v in enumerate(values)]
        return pd.DataFrame(rows)

    def test_returns_none_when_fewer_than_13(self):
        from utils.market import yoy_change
        df = self._make_df([100] * 12)
        assert yoy_change(df, "Steel") is None

    def test_correct_yoy(self):
        from utils.market import yoy_change
        # 13 values: index 0 = prev year, index -1 = latest
        values = [100] + [105] * 11 + [110]
        df = self._make_df(values)
        result = yoy_change(df, "Steel")
        assert result == pytest.approx(0.10)  # (110-100)/100

    def test_unknown_series_returns_none(self):
        from utils.market import yoy_change
        df = self._make_df([100] * 13)
        assert yoy_change(df, "Copper") is None

    def test_zero_prev_returns_none(self):
        from utils.market import yoy_change
        values = [0] + [100] * 12
        df = self._make_df(values)
        assert yoy_change(df, "Steel") is None


# ---------------------------------------------------------------------------
# utils.quotes
# ---------------------------------------------------------------------------

class TestBestQuotes:
    def test_preferred_wins(self):
        from utils.quotes import best_quotes
        q = pd.DataFrame({
            "material_id": ["M1", "M1"],
            "supplier": ["A", "B"],
            "price_eur_per_kg": [5.0, 3.0],
            "lead_time_days": [10, 5],
            "preferred": [1, 0],
        })
        result = best_quotes(q)
        assert result.iloc[0]["supplier"] == "A"

    def test_lowest_price_when_equal_preference(self):
        from utils.quotes import best_quotes
        q = pd.DataFrame({
            "material_id": ["M1", "M1"],
            "supplier": ["A", "B"],
            "price_eur_per_kg": [5.0, 3.0],
            "lead_time_days": [10, 10],
            "preferred": [0, 0],
        })
        result = best_quotes(q)
        assert result.iloc[0]["price_eur_per_kg"] == 3.0

    def test_one_per_material(self):
        from utils.quotes import best_quotes
        q = pd.DataFrame({
            "material_id": ["M1", "M1", "M2", "M2"],
            "supplier": ["A", "B", "C", "D"],
            "price_eur_per_kg": [5.0, 3.0, 8.0, 7.0],
            "lead_time_days": [10, 5, 3, 2],
            "preferred": [0, 0, 0, 0],
        })
        result = best_quotes(q)
        assert len(result) == 2
        assert set(result["material_id"]) == {"M1", "M2"}


class TestApplyBestQuotes:
    def test_fills_price_from_quote(self):
        from utils.quotes import apply_best_quotes
        mats = pd.DataFrame({"material_id": ["M1"], "price_eur_per_kg": [None]})
        quotes = pd.DataFrame({
            "material_id": ["M1"],
            "supplier": ["S"],
            "price_eur_per_kg": [9.0],
            "lead_time_days": [5],
            "preferred": [1],
        })
        result = apply_best_quotes(mats, quotes)
        assert result.iloc[0]["price_eur_per_kg"] == pytest.approx(9.0)

    def test_keeps_existing_price_when_not_null(self):
        from utils.quotes import apply_best_quotes
        mats = pd.DataFrame({"material_id": ["M1"], "price_eur_per_kg": [7.0]})
        quotes = pd.DataFrame({
            "material_id": ["M1"],
            "supplier": ["S"],
            "price_eur_per_kg": [9.0],
            "lead_time_days": [5],
            "preferred": [1],
        })
        result = apply_best_quotes(mats, quotes)
        assert result.iloc[0]["price_eur_per_kg"] == pytest.approx(7.0)


class TestJoinWithMaterials:
    def test_replaces_price_column(self):
        from utils.quotes import join_with_materials
        mats = pd.DataFrame({"material_id": ["M1"], "price_eur_per_kg": [5.0], "description": ["steel"]})
        best = pd.DataFrame({
            "material_id": ["M1"],
            "supplier": ["S"],
            "price_eur_per_kg": [9.0],
            "lead_time_days": [3],
        })
        result = join_with_materials(mats, best)
        assert result.iloc[0]["price_eur_per_kg"] == pytest.approx(9.0)
        assert result.iloc[0]["supplier"] == "S"


# ---------------------------------------------------------------------------
# utils.presets
# ---------------------------------------------------------------------------

class TestPresets:
    def test_load_defaults_when_no_file(self, tmp_path, monkeypatch):
        from utils import presets as p_mod
        monkeypatch.setattr(p_mod, "PRESETS_FILE", tmp_path / "nonexistent.json")
        result = p_mod.load_presets()
        assert "Standard" in result
        assert result["Standard"].overhead_pct == pytest.approx(0.20)

    def test_save_and_reload(self, tmp_path, monkeypatch):
        from utils import presets as p_mod
        from utils.presets import PricingPreset
        monkeypatch.setattr(p_mod, "PRESETS_FILE", tmp_path / "presets.json")
        data = {"Custom": PricingPreset("Custom", 0.30, 0.12)}
        p_mod.save_presets(data)
        loaded = p_mod.load_presets()
        assert "Custom" in loaded
        assert loaded["Custom"].margin_pct == pytest.approx(0.12)

    def test_preset_dataclass_fields(self):
        from utils.presets import PricingPreset
        p = PricingPreset("Test", 0.1, 0.2)
        assert p.name == "Test"
        assert p.overhead_pct == 0.1
        assert p.margin_pct == 0.2


# ---------------------------------------------------------------------------
# utils.routing
# ---------------------------------------------------------------------------

class TestComputeRoutingCost:
    def _frames(self):
        bom = pd.DataFrame({
            "line_id": ["L1", "L2"],
            "material_id": ["M1", "M2"],
            "process_route": ["P1", "P2"],
            "qty": [2, 3],
        })
        routing = pd.DataFrame({
            "process_id": ["P1", "P2"],
            "time_h_per_unit": [0.5, 1.0],
            "setup_h": [0.25, 0.0],
        })
        return bom, routing

    def test_routing_time_calculated(self):
        from utils.routing import compute_routing_cost
        bom, routing = self._frames()
        df = compute_routing_cost(bom, routing)
        # P1: 0.5*2 + 0.25 = 1.25
        assert df[df["process_route"] == "P1"]["routing_time_h"].iloc[0] == pytest.approx(1.25)
        # P2: 1.0*3 + 0.0 = 3.0
        assert df[df["process_route"] == "P2"]["routing_time_h"].iloc[0] == pytest.approx(3.0)

    def test_missing_process_route_gives_zero(self):
        from utils.routing import compute_routing_cost
        bom = pd.DataFrame({"line_id": ["L1"], "process_route": ["UNKNOWN"], "qty": [1]})
        routing = pd.DataFrame({"process_id": ["P1"], "time_h_per_unit": [1.0], "setup_h": [0.0]})
        df = compute_routing_cost(bom, routing)
        assert df["routing_time_h"].iloc[0] == pytest.approx(0.0)


class TestRoutingSummary:
    def test_sums_by_process(self):
        from utils.routing import routing_summary
        df = pd.DataFrame({
            "process_id": ["P1", "P1", "P2"],
            "routing_time_h": [1.0, 2.0, 3.0],
        })
        summary = routing_summary(df)
        p1 = summary[summary["process_id"] == "P1"]["routing_time_h"].iloc[0]
        assert p1 == pytest.approx(3.0)

    def test_no_column_returns_empty(self):
        from utils.routing import routing_summary
        df = pd.DataFrame({"process_id": ["P1"]})
        result = routing_summary(df)
        assert list(result.columns) == ["process_id", "routing_time_h"]
        assert len(result) == 0


# ---------------------------------------------------------------------------
# utils.history  (pure logic, no filesystem I/O)
# ---------------------------------------------------------------------------

class TestFindAnomalies:
    def _diff_df(self):
        return pd.DataFrame({
            "material_id": ["M1", "M2", "M3"],
            "old_price": [100.0, 100.0, 100.0],
            "new_price": [130.0, 105.0, 60.0],
            "pct_change": [0.30, 0.05, -0.40],
        })

    def test_finds_large_changes(self):
        from utils.history import find_anomalies, AnomalyConfig
        result = find_anomalies(self._diff_df(), AnomalyConfig(threshold_pct=0.25))
        ids = set(result["material_id"])
        assert "M1" in ids   # +30%
        assert "M3" in ids   # -40%
        assert "M2" not in ids  # only 5%

    def test_empty_df_returns_empty(self):
        from utils.history import find_anomalies
        empty = pd.DataFrame(columns=["material_id", "old_price", "new_price", "pct_change"])
        result = find_anomalies(empty)
        assert len(result) == 0

    def test_sorted_by_abs_pct_descending(self):
        from utils.history import find_anomalies, AnomalyConfig
        result = find_anomalies(self._diff_df(), AnomalyConfig(threshold_pct=0.0))
        assert result["abs_pct"].is_monotonic_decreasing


class TestListAndLatestSnapshot:
    def test_empty_when_dir_missing(self, monkeypatch):
        from utils import history as h_mod
        monkeypatch.setattr(h_mod, "HISTORY_DIR", Path("/nonexistent/history"))
        assert h_mod.list_snapshots() == []
        assert h_mod.latest_snapshot() is None

    def test_lists_and_sorts(self, tmp_path, monkeypatch):
        from utils import history as h_mod
        monkeypatch.setattr(h_mod, "HISTORY_DIR", tmp_path)
        (tmp_path / "materials_20240101.csv").write_text("material_id,price_eur_per_kg\nM1,5\n")
        (tmp_path / "materials_20240201.csv").write_text("material_id,price_eur_per_kg\nM1,6\n")
        snaps = h_mod.list_snapshots()
        assert len(snaps) == 2
        assert snaps[0].name < snaps[1].name  # sorted ascending

    def test_latest_returns_last(self, tmp_path, monkeypatch):
        from utils import history as h_mod
        monkeypatch.setattr(h_mod, "HISTORY_DIR", tmp_path)
        (tmp_path / "materials_20240101.csv").write_text("material_id\nM1\n")
        (tmp_path / "materials_20240301.csv").write_text("material_id\nM1\n")
        latest = h_mod.latest_snapshot()
        assert latest is not None
        assert "20240301" in latest.name


class TestBuildHistoryDf:
    def test_no_snapshots_returns_empty(self, monkeypatch):
        from utils import history as h_mod
        monkeypatch.setattr(h_mod, "HISTORY_DIR", Path("/nonexistent"))
        df = h_mod.build_history_df()
        assert df.empty

    def test_builds_from_snapshots(self, tmp_path, monkeypatch):
        from utils import history as h_mod
        monkeypatch.setattr(h_mod, "HISTORY_DIR", tmp_path)
        snap1 = tmp_path / "materials_20240101.csv"
        snap1.write_text("material_id,description,price_eur_per_kg\nM1,Steel,5.0\n")
        snap2 = tmp_path / "materials_20240201.csv"
        snap2.write_text("material_id,description,price_eur_per_kg\nM1,Steel,6.0\n")
        df = h_mod.build_history_df()
        assert len(df) == 2
        assert set(df["material_id"]) == {"M1"}
        assert list(df["price_eur_per_kg"]) == [5.0, 6.0]

    def test_filters_by_material_id(self, tmp_path, monkeypatch):
        from utils import history as h_mod
        monkeypatch.setattr(h_mod, "HISTORY_DIR", tmp_path)
        snap = tmp_path / "materials_20240101.csv"
        snap.write_text("material_id,price_eur_per_kg\nM1,5.0\nM2,7.0\n")
        df = h_mod.build_history_df(["M1"])
        assert all(df["material_id"] == "M1")


# ---------------------------------------------------------------------------
# utils.io
# ---------------------------------------------------------------------------

class TestReadCsv:
    def test_reads_with_schema(self, tmp_path):
        from utils.io import _read_csv, SCHEMA_MATERIALS
        p = tmp_path / "mat.csv"
        p.write_text("material_id,description,price_eur_per_kg\nM1,Steel,5.0\n")
        df = _read_csv(p, SCHEMA_MATERIALS)
        assert str(df["material_id"].dtype) in ("object", "string")  # pandas string dtype
        assert df["price_eur_per_kg"].dtype == "float64"

    def test_reads_without_schema(self, tmp_path):
        from utils.io import _read_csv
        p = tmp_path / "plain.csv"
        p.write_text("a,b\n1,2\n")
        df = _read_csv(p)
        assert list(df.columns) == ["a", "b"]
