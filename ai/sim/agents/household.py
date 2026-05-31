from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Household:
    """Represents a family or co-living unit sharing resources.

    See implementation plan for joint constraints like car-sharing.
    """

    id: int
    member_ids: list[int] = field(default_factory=list)
    has_car: bool = False
    cars_owned: int = 0
    cars_available: int = 0

    def reset_daily_resources(self) -> None:
        """Reset shared resources at the beginning of each day."""
        self.cars_available = self.cars_owned

    def request_car(self) -> bool:
        """Attempt to claim a car for a commute. Returns True if successful."""
        if self.cars_available > 0:
            self.cars_available -= 1
            return True
        return False

    def release_car(self) -> None:
        """Return a car to the household resource pool."""
        if self.cars_available < self.cars_owned:
            self.cars_available += 1
