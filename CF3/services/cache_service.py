from __future__ import annotations

from functools import lru_cache


class CacheService:
    @staticmethod
    @lru_cache(maxsize=32)
    def cached_exchange_rate(currency: str) -> float:
        defaults = {
            'EUR': 1.0,
            'USD': 1.08,
            'GBP': 0.86,
        }

        return defaults.get(currency.upper(), 1.0)
