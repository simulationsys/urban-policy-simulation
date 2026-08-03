"""Ride-hail (Ola/Uber) surge pricing model.

Computes a dynamic surge multiplier based on:
- Time-of-day (peak hour bonus)
- Rain intensity (exposed passengers prefer ride-hail → demand spike)
- Demand/supply ratio (more ride requests than available drivers)

The multiplier is capped at a regulatory maximum (Delhi context: ≤3.5×).

Usage::

    surge = RideHailSurge()
    mult = surge.surge_multiplier(hour=9, rain_intensity=0.7, demand_ratio=1.8)
    fare = surge.fare(distance_km=12.0, multiplier=mult)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RideHailSurge:
    """Dynamic surge pricing model for Ola/Uber-style ride-hail services.

    Attributes:
        base_fare_per_km: Base fare per kilometre in ₹ (before surge).
        base_min_fare: Minimum fare in ₹ regardless of distance.
        peak_windows: Tuples of (start_hour, end_hour) for AM/PM peak periods.
        peak_bonus: Additive surge bonus applied during peak windows.
        rain_surge_coeff: Coefficient controlling how much rain increases surge.
        demand_surge_coeff: Coefficient controlling how excess demand increases surge.
        max_surge_cap: Hard regulatory cap on the surge multiplier.
    """

    base_fare_per_km: float = 12.0
    base_min_fare: float = 30.0
    peak_windows: tuple[tuple[int, int], ...] = ((8, 10), (17, 20))
    peak_bonus: float = 0.3
    rain_surge_coeff: float = 0.8
    demand_surge_coeff: float = 1.5
    max_surge_cap: float = 3.5

    def _is_peak(self, hour: int) -> bool:
        """Check if the given hour falls within any peak window."""
        return any(start <= hour < end for start, end in self.peak_windows)

    def surge_multiplier(
        self,
        hour: int,
        rain_intensity: float = 0.0,
        demand_ratio: float = 1.0,
    ) -> float:
        """Compute the surge multiplier.

        Args:
            hour: Current hour of day (0–23).
            rain_intensity: Rain intensity in [0, 1]. 0 = dry, 1 = heavy downpour.
            demand_ratio: Ratio of ride requests to available drivers.
                          1.0 = balanced, >1.0 = excess demand.

        Returns:
            Surge multiplier ≥ 1.0, capped at ``max_surge_cap``.
        """
        multiplier = 1.0

        # Peak-hour bonus
        if self._is_peak(hour):
            multiplier += self.peak_bonus

        # Rain-driven demand spike
        multiplier += self.rain_surge_coeff * max(0.0, rain_intensity)

        # Demand/supply imbalance (only kicks in above equilibrium)
        multiplier += self.demand_surge_coeff * max(0.0, demand_ratio - 1.0)

        return min(multiplier, self.max_surge_cap)

    def fare(self, distance_km: float, multiplier: float = 1.0) -> float:
        """Compute the ride-hail fare in ₹.

        Args:
            distance_km: Trip distance in kilometres.
            multiplier: Surge multiplier (from ``surge_multiplier()``).

        Returns:
            Fare in ₹, at least ``base_min_fare``.
        """
        raw = self.base_fare_per_km * distance_km * multiplier
        return max(self.base_min_fare, raw)
