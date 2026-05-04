from dataclasses import dataclass
from datetime import datetime, timezone

from ..services.dk_energy import get_dk_hourly
from ..services.pv_power import get_power
from ..services.price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data


def _hour_floor(dt: datetime) -> datetime:
    """Strip minutes and seconds so that e.g. 14:23 and 14:59 map to the same key (14:00)."""
    return dt.replace(minute=0, second=0, microsecond=0)


@dataclass
class _CarbonCacheEntry:
    data: list[tuple[datetime, int]]


@dataclass
class _PriceCacheEntry:
    data: list[tuple[datetime, float]]


@dataclass
class _PowerCacheEntry:
    data: list[tuple[datetime, float]]


class MarketDataStore:
    """In-memory store for hourly market data, keyed on simulated time."""

    def __init__(self):
        """Init."""
        self._carbon: dict[tuple[str, datetime], _CarbonCacheEntry] = {}
        self._price: dict[tuple[str, datetime], _PriceCacheEntry] = {}
        self._power: dict[tuple[str, float, datetime], _PowerCacheEntry] = {}

    def get_carbon(
        self,
        start: datetime,
        end: datetime,
        zone: str,
    ) -> list[tuple[datetime, int]]:
        """Return grid carbon intensity for the simulated hour.

        Fetches from the Electricity Maps API only when the simulated hour
        changes; subsequent calls within the same hour return cached data.
        """
        key = (zone.upper(), _hour_floor(start))

        entry = self._carbon.get(key)
        if entry is not None:
            return entry.data

        data = fetch_carbon_intensity(start, end, zone)
        self._carbon[key] = _CarbonCacheEntry(data=data)
        return data

    def get_price(
        self,
        start: datetime,
        end: datetime,
        zone: str,
    ) -> list[tuple[datetime, float]]:
        """Return day-ahead electricity price for the simulated hour.

        Fetches from the Electricity Maps API only when the simulated hour
        changes; subsequent calls within the same hour return cached data.
        """
        key = (zone.upper(), _hour_floor(start))

        entry = self._price.get(key)
        if entry is not None:
            return entry.data

        data = fetch_price_data(start, end, zone)
        self._price[key] = _PriceCacheEntry(data=data)
        return data

    def get_power(
        self,
        start: datetime,
        end: datetime,
        zone: str,
        pv_capacity_w: float,
    ) -> list[tuple[datetime, float]]:
        """Return solar generation in watts for the simulated hour.

        For DK zones, real measured generation is fetched from the AAU Orin
        proxy (CrateDB) instead of the static CSV capacity-factor table.

        For all other zones, generation is estimated from a static CSV of
        historical PV capacity factors multiplied by the installed capacity.

        Fetches only when the simulated hour changes; subsequent calls within
        the same hour return cached data.
        """
        zone_key = zone.upper()
        key = (zone_key, float(pv_capacity_w), _hour_floor(start))

        entry = self._power.get(key)
        if entry is not None:
            return entry.data

        if zone_key.startswith("DK"):
            dk_hourly = get_dk_hourly(start, end)
            data = [
                (
                    datetime.strptime(r["timestamp"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc),
                    float(r["avg_generation_w"]),
                )
                for r in dk_hourly
            ]
        else:
            data = get_power(start, end, zone, pv_capacity_w)

        self._power[key] = _PowerCacheEntry(data=data)
        return data


market_data_store = MarketDataStore()
