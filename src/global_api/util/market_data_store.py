from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..services.pv_power import get_power
from ..services.price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data


@dataclass
class _CarbonCacheEntry:
    data: list[tuple[datetime, int]]
    last_updated: datetime


@dataclass
class _PriceCacheEntry:
    data: list[tuple[datetime, float]]
    last_updated: datetime


@dataclass
class _PvCacheEntry:
    data: list[tuple[datetime, float]]
    last_updated: datetime


class MarketDataStore:
    """In-memory store for hourly market data."""

    def __init__(self):
        self._carbon_by_zone: dict[str, _CarbonCacheEntry] = {}
        self._price_by_zone: dict[str, _PriceCacheEntry] = {}
        self._pv_by_zone_and_capacity: dict[tuple[str, float], _PvCacheEntry] = {}
        self._ttl = timedelta(hours=1)
    # Time to live (TTL)
    def _is_stale(self, last_updated: datetime, now: datetime) -> bool:
        """Check if the data is cached more than the accepted hour."""
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

    def get_power(
        self,
        start: datetime,
        end: datetime,
        zone: str,
        pv_capacity_w: float,
    ) -> list[tuple[datetime, float]]:
        """Return PV power from memory unless older than one hour."""
        cache_key = (zone.upper(), float(pv_capacity_w))
        now = datetime.now(timezone.utc)

        entry = self._pv_by_zone_and_capacity.get(cache_key)
        if entry is not None and not self._is_stale(entry.last_updated, now):
            return entry.data

        data = get_power(start, end, zone, pv_capacity_w)
        self._pv_by_zone_and_capacity[cache_key] = _PvCacheEntry(data=data, last_updated=now)
        return data


market_data_store = MarketDataStore()
