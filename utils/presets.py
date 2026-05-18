import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

PRESETS_FILE = Path("data/presets.json")


@dataclass
class PricingPreset:
    name: str
    overhead_pct: float
    margin_pct: float


DEFAULTS: Dict[str, PricingPreset] = {
    "Standard": PricingPreset("Standard", 0.20, 0.10),
    "Aggressive": PricingPreset("Aggressive", 0.15, 0.05),
    "Premium": PricingPreset("Premium", 0.25, 0.15),
}


def load_presets() -> Dict[str, PricingPreset]:
    if not PRESETS_FILE.exists():
        return DEFAULTS.copy()
    try:
        data = json.loads(PRESETS_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Presets file must contain a JSON object")
        result: Dict[str, PricingPreset] = {}
        for k, v in data.items():
            if not isinstance(v, dict):
                logger.warning("Skipping malformed preset %r", k)
                continue
            result[str(k)] = PricingPreset(
                name=str(v.get("name", k)),
                overhead_pct=float(v.get("overhead_pct", 0.20)),
                margin_pct=float(v.get("margin_pct", 0.10)),
            )
        return result if result else DEFAULTS.copy()
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("Presets file corrupt, falling back to defaults", exc_info=True)
        return DEFAULTS.copy()


def save_presets(presets: Dict[str, PricingPreset]) -> None:
    PRESETS_FILE.write_text(
        json.dumps({k: asdict(v) for k, v in presets.items()}, indent=2), encoding="utf-8"
    )
