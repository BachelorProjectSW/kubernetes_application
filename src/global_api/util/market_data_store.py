from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..services.price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data


@dataclass
class _CarbonCacheEntry:
    data: list[tuple[datetime, int]]
    last_updated: datetime


@dataclass
class _PriceCacheEntry:
    data: list[tuple[datetime, float]]
    last_updated: datetime


class MarketDataStore:
    """In-memory store for hourly market data."""

    def __init__(self):
        self._carbon_by_zone: dict[str, _CarbonCacheEntry] = {}
        self._price_by_zone: dict[str, _PriceCacheEntry] = {}
        self._ttl = timedelta(hours=1)

    def _is_stale(self, last_updated: datetime, now: datetime) -> bool:
        return now - last_updated >= self._ttl

    def get_carbon(self, start: datetime, end: datetime, zone: str) -> list[tuple[datetime, int]]:
        """Return carbon data from memory unless older than one hour."""
        zone_key = zone.upper()
        now = datetime.now(timezone.utc)

        entry = self._carbon_by_zone.get(zone_key)
        if entry is not None and not self._is_stale(entry.last_updated, now):
            return entry.data

        data = fetch_carbon_intensity(start, end, zone)
        self._carbon_by_zone[zone_key] = _CarbonCacheEntry(data=data, last_updated=now)
        return data

    def get_price(self, start: datetime, end: datetime, zone: str) -> list[tuple[datetime, float]]:
        """Return price data from memory unless older than one hour."""
        zone_key = zone.upper()
        now = datetime.now(timezone.utc)

        entry = self._price_by_zone.get(zone_key)
        if entry is not None and not self._is_stale(entry.last_updated, now):
            return entry.data

        data = fetch_price_data(start, end, zone)
        self._price_by_zone[zone_key] = _PriceCacheEntry(data=data, last_updated=now)
        return data


market_data_store = MarketDataStore()
