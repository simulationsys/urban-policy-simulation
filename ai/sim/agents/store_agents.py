"""Formal retail agents — store managers and store staff.

Models fixed-location retail with:
- StoreManager: weekly pricing/restocking decisions, shift assignment.
- StoreStaff: shift-dictated schedules, lateness frustration from commute delays.

See ``gemini-code-1780254276846.md`` §2 for requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sim.agents.memory import AgentMemory
from sim.agents.modes import Occupation
from sim.agents.retail_memory import RetailMemory
from sim.agents.schedule import Activity, ActivitySchedule, ActivityType

NodeID = int


# ------------------------------------------------------------------ #
# Shift
# ------------------------------------------------------------------ #


@dataclass
class Shift:
    """A single work shift assigned by a store manager."""

    start_time_min: int  # minutes since midnight
    end_time_min: int
    staff_id: int


# ------------------------------------------------------------------ #
# Store Manager
# ------------------------------------------------------------------ #


@dataclass
class StoreManager:
    """Manager of a formal retail store.

    Responsibilities:
    - Assign shifts to ``StoreStaff`` members.
    - Decide on restocking (weekly) and pricing adjustments.

    Attributes:
        id: Unique agent identifier.
        store_node: Fixed location of the store.
        staff_ids: IDs of ``StoreStaff`` reporting to this manager.
        pricing_strategy: Markup multiplier on base cost (1.0 = no markup).
        restock_day: Day of week to restock (0 = Monday … 6 = Sunday).
        inventory: Normalised stock level (0.0 = empty, 1.0 = full).
        retail_memory: Rolling sales memory for business decisions.
    """

    id: int
    store_node: NodeID
    staff_ids: list[int] = field(default_factory=list)
    pricing_strategy: float = 1.2  # 20 % markup by default
    restock_day: int = 0  # Monday
    inventory: float = 1.0
    retail_memory: RetailMemory = field(default_factory=RetailMemory)
    occupation: Occupation = Occupation.STORE_MANAGER

    # ------------------------------------------------------------------ #
    # Shift assignment
    # ------------------------------------------------------------------ #

    def assign_shifts(
        self,
        staff: list[StoreStaff],
        *,
        shift_start: int = 9 * 60,
        shift_end: int = 17 * 60,
    ) -> list[Shift]:
        """Assign identical shifts to all staff and update their schedules.

        Args:
            staff: List of ``StoreStaff`` to schedule.
            shift_start: Shift start in minutes since midnight (default 09:00).
            shift_end: Shift end in minutes since midnight (default 17:00).

        Returns:
            The list of ``Shift`` objects created.
        """
        shifts: list[Shift] = []
        for s in staff:
            shift = Shift(
                start_time_min=shift_start,
                end_time_min=shift_end,
                staff_id=s.id,
            )
            s.assigned_shift = shift
            s.build_schedule_from_shift(shift)
            shifts.append(shift)
        return shifts

    # ------------------------------------------------------------------ #
    # Restocking
    # ------------------------------------------------------------------ #

    def maybe_restock(self, current_day: int) -> bool:
        """Restock inventory on the configured restock day.

        Args:
            current_day: Day of week (0 = Monday … 6 = Sunday).

        Returns:
            True if restocking occurred.
        """
        if current_day == self.restock_day:
            self.inventory = 1.0
            return True
        return False

    # ------------------------------------------------------------------ #
    # Pricing
    # ------------------------------------------------------------------ #

    def adjust_pricing(self) -> None:
        """Adjust pricing strategy based on recent sales trend.

        If average revenue is declining (below previous window), increase
        discount slightly; if strong, maintain or increase markup.
        """
        avg = self.retail_memory.avg_revenue()
        if avg is None:
            return

        if len(self.retail_memory.sales_history) >= 2:
            recent = list(self.retail_memory.sales_history)
            midpoint = len(recent) // 2
            first_half_avg = (
                sum(o.revenue for o in recent[:midpoint]) / midpoint
                if midpoint > 0
                else avg
            )
            second_half_avg = (
                sum(o.revenue for o in recent[midpoint:]) / (len(recent) - midpoint)
            )

            if second_half_avg < first_half_avg * 0.85:
                # Sales declining → reduce markup to attract customers
                self.pricing_strategy = max(1.0, self.pricing_strategy - 0.05)
            elif second_half_avg > first_half_avg * 1.15:
                # Sales growing → increase markup slightly
                self.pricing_strategy = min(2.0, self.pricing_strategy + 0.05)


# ------------------------------------------------------------------ #
# Store Staff
# ------------------------------------------------------------------ #


@dataclass
class StoreStaff:
    """An employee of a formal retail store.

    Their daily schedule is dictated by the ``Shift`` assigned by the
    ``StoreManager``. Lateness frustration increases if commute delays
    cause them to arrive after shift start.

    Attributes:
        id: Unique agent identifier.
        home_node: Where the staff member lives.
        store_node: Fixed location they commute to.
        assigned_shift: Currently assigned shift (set by StoreManager).
        schedule: Daily activity schedule built from the shift.
        memory: Standard commute memory (reuses ``AgentMemory``).
        lateness_frustration: Cumulative lateness frustration [0.0, 5.0].
    """

    id: int
    home_node: NodeID
    store_node: NodeID
    assigned_shift: Shift | None = None
    schedule: ActivitySchedule = field(default_factory=ActivitySchedule)
    memory: AgentMemory = field(default_factory=AgentMemory)
    occupation: Occupation = Occupation.STORE_STAFF
    lateness_frustration: float = 0.0

    # ------------------------------------------------------------------ #
    # Schedule building
    # ------------------------------------------------------------------ #

    def build_schedule_from_shift(self, shift: Shift) -> None:
        """Construct a Home → Work → Home schedule from the assigned shift.

        The schedule assumes the staff member leaves home 60 minutes before
        shift start (to allow for commute).
        """
        commute_buffer = 60  # minutes
        leave_home = max(0, shift.start_time_min - commute_buffer)
        work_duration = shift.end_time_min - shift.start_time_min

        self.schedule = ActivitySchedule(
            activities=[
                Activity(
                    ActivityType.HOME,
                    self.home_node,
                    start_time_min=0,
                    duration_min=leave_home,
                ),
                Activity(
                    ActivityType.WORK,
                    self.store_node,
                    start_time_min=shift.start_time_min,
                    duration_min=work_duration,
                ),
                Activity(
                    ActivityType.HOME,
                    self.home_node,
                    start_time_min=shift.end_time_min,
                    duration_min=24 * 60 - shift.end_time_min,
                ),
            ],
            leave_home_min=leave_home,
            work_duration_min=work_duration,
        )

    # ------------------------------------------------------------------ #
    # Lateness tracking
    # ------------------------------------------------------------------ #

    def record_arrival(self, actual_arrival_min: int) -> None:
        """Record the actual arrival time and update lateness frustration.

        If the staff member arrives after their shift start time,
        frustration increments by 0.5. Otherwise it cools down by 0.2.

        Args:
            actual_arrival_min: Arrival time in minutes since midnight.
        """
        if self.assigned_shift is None:
            return

        if actual_arrival_min > self.assigned_shift.start_time_min:
            self.lateness_frustration = min(5.0, self.lateness_frustration + 0.5)
        else:
            self.lateness_frustration = max(0.0, self.lateness_frustration - 0.2)
