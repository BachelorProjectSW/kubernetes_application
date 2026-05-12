from dataclasses import dataclass
from datetime import datetime, timezone

from ..services.dk_energy import get_dk_hourly
from ..services.pv_power import get_power
from ..services.price_and_carbon_intensity import fetch_carbon_intensity, fetch_price_data


def _hour_floor(dt: datetime) -> datetime:
    """Normalize a timestamp to the beginning of its hour.

    Args:
        dt: Timestamp to normalize.

    Returns:
        datetime: Timestamp with minute, second, and microsecond set to zero.
    """
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
        """Initialize empty in-memory caches for market data.

        Returns:
            None: Sets up cache dictionaries for carbon, price, and power
            time-series values.
        """
        self._carbon: dict[tuple[str, datetime], _CarbonCacheEntry] = {}
        self._price: dict[tuple[str, datetime], _PriceCacheEntry] = {}
        self._power: dict[tuple[str, float, datetime], _PowerCacheEntry] = {}

    def reset(self):
        """Clear all cached market data.

        This should be called when a new test starts to avoid reusing cached
        values from a previous run.

        Returns:
            None: Empties all internal cache dictionaries.
        """
        self._carbon.clear()
        self._price.clear()
        self._power.clear()

    def get_carbon(
        self,
        start: datetime,
        end: datetime,
        zone: str,
    ) -> list[tuple[datetime, int]]:
        """Get grid carbon intensity for the simulated time window.

        Fetches from the Electricity Maps API only when the simulated hour
        changes; subsequent calls within the same hour return cached data.

        Args:
            start: Start timestamp of the simulated interval.
            end: End timestamp of the simulated interval.
            zone: Electricity Maps zone code.

        Returns:
            list[tuple[datetime, int]]: Carbon intensity series in gCO2eq/kWh.

        Raises:
            Exception: Propagates provider errors from
                ``fetch_carbon_intensity``.
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
        """Get day-ahead electricity price for the simulated time window.

        Fetches from the Electricity Maps API only when the simulated hour
        changes; subsequent calls within the same hour return cached data.

        Args:
            start: Start timestamp of the simulated interval.
            end: End timestamp of the simulated interval.
            zone: Electricity Maps zone code.

        Returns:
            list[tuple[datetime, float]]: Price series for the given zone.

        Raises:
            Exception: Propagates provider errors from ``fetch_price_data``.
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
        """Get PV generation in watts for the simulated time window.

        For DK zones, real measured generation is fetched from the AAU Orin
        proxy (CrateDB) instead of the static CSV capacity-factor table.

        For all other zones, generation is estimated from a static CSV of
        historical PV capacity factors multiplied by the installed capacity.

        Fetches only when the simulated hour changes; subsequent calls within
        the same hour return cached data.

        Args:
            start: Start timestamp of the simulated interval.
            end: End timestamp of the simulated interval.
            zone: Country or zone code used for data lookup.
            pv_capacity_w: Installed PV capacity in watts.

        Returns:
            list[tuple[datetime, float]]: PV generation time series in watts.

        Raises:
            Exception: Propagates errors from DK proxy fetches or CSV-based
                power lookup.
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
