"""Deterministic stub simulation engine.

This is **not** the real model — it is a placeholder so the backend, WebSocket stream, and frontend
can be built and demoed before SUB-01 exists. It produces structurally plausible dynamics:

- A daily commute curve (morning + evening peaks).
- Rain that pushes mode share away from walk/bike toward metro/auto and lifts commute time and
  congestion — the causal story from PROJECT_SPEC §3.2.
- Response to injected events (rain, bus capacity, fuel price, metro line shutdown).

Everything derives from a single seeded RNG (PROJECT_SPEC §8.4): same config + seed → same run.
No NumPy dependency on purpose — keeps the backend lean (uses only the stdlib).
"""

from __future__ import annotations

import math
import random

from app.models.schemas import (
    AggregateMetrics,
    Event,
    EventType,
    GridCell,
    Mode,
    ScenarioConfig,
    ScenarioStatus,
    Snapshot,
)

# Coarse map grid centered on the chosen city — Delhi (Rajiv Chowk).
_GRID_ROWS, _GRID_COLS = 10, 10
_CITY_CENTER = {"delhi": (28.6328, 77.2197)}


class FakeSimEngine:
    """Implements the ``SimEngine`` Protocol with cheap analytic dynamics."""

    def __init__(self, config: ScenarioConfig) -> None:
        self.config = config
        self._tick = 0
        self._rng = random.Random(config.seed)

        # Mutable world parameters that events can change.
        self._rain = float(config.params.get("rain_intensity", 0.0))
        self._rain_ticks_left = 0
        self._bus_capacity_mult = float(config.params.get("bus_capacity_pct", 1.0))
        self._fuel_price_delta_paise = int(config.params.get("fuel_price_delta_paise", 0))
        self._disabled_metro_lines: set[str] = set()

        self._pending: list[Event] = []
        clat, clon = _CITY_CENTER.get(config.city, (28.6328, 77.2197))
        self._cells = [
            GridCell(lat=clat + (r - _GRID_ROWS / 2) * 0.01, lon=clon + (c - _GRID_COLS / 2) * 0.01)
            for r in range(_GRID_ROWS)
            for c in range(_GRID_COLS)
        ]

    # --- SimEngine Protocol --------------------------------------------------------------
    @property
    def current_tick(self) -> int:
        return self._tick

    def queue_event(self, event: Event) -> int:
        self._pending.append(event)
        return self._tick + 1

    def step(self) -> Snapshot:
        self._tick += 1
        self._apply_pending_events()
        self._advance_weather()
        self._update_grid()
        return self.snapshot()

    def snapshot(self) -> Snapshot:
        return Snapshot(
            scenario_id="",  # filled in by the scenario manager
            tick=self._tick,
            sim_time_minutes=self._tick * self.config.tick_minutes,
            status=ScenarioStatus.running,
            metrics=self._compute_metrics(),
            grid=list(self._cells),
        )

    # --- internals -----------------------------------------------------------------------
    def _apply_pending_events(self) -> None:
        for ev in self._pending:
            p = ev.payload
            if ev.type is EventType.weather:
                self._rain = float(p.get("rain_intensity", self._rain))
                self._rain_ticks_left = int(p.get("duration_ticks", 0))
            elif ev.type is EventType.policy:
                if "bus_capacity_pct" in p:
                    self._bus_capacity_mult = float(p["bus_capacity_pct"])
                if "fuel_price_delta_paise" in p:
                    self._fuel_price_delta_paise = int(p["fuel_price_delta_paise"])
            elif ev.type is EventType.infrastructure:
                line = p.get("disable_metro_line")
                if isinstance(line, str):
                    self._disabled_metro_lines.add(line)
                line = p.get("enable_metro_line")
                if isinstance(line, str):
                    self._disabled_metro_lines.discard(line)
        self._pending.clear()

    def _advance_weather(self) -> None:
        if self._rain_ticks_left > 0:
            self._rain_ticks_left -= 1
            if self._rain_ticks_left == 0:
                self._rain = 0.0

    def _day_phase(self) -> float:
        """Commute intensity in [0,1] across a 24h day with morning/evening peaks."""
        minutes = (self._tick * self.config.tick_minutes) % (24 * 60)
        hour = minutes / 60.0
        morning = math.exp(-((hour - 9.0) ** 2) / 2.0)
        evening = math.exp(-((hour - 18.0) ** 2) / 2.5)
        return min(1.0, morning + evening)

    def _compute_metrics(self) -> AggregateMetrics:
        phase = self._day_phase()
        jitter = self._rng.uniform(-0.03, 0.03)

        # Rain and fuel price shift mode share. Metro shutdown pushes load to bus/road.
        rain = self._rain
        metro_penalty = 0.25 if self._disabled_metro_lines else 0.0
        fuel_push = min(0.15, self._fuel_price_delta_paise / 20_000)  # ₹20 ~= full push

        walk = max(0.02, 0.12 - 0.06 * rain + jitter)
        bike = max(0.02, 0.10 - 0.07 * rain + jitter)
        car = max(0.05, 0.22 - 0.05 * rain - fuel_push + jitter)
        metro = max(0.05, 0.26 + 0.12 * rain + 0.5 * fuel_push - metro_penalty + jitter)
        bus = (
            max(0.05, 0.18 + 0.04 * rain + 0.4 * fuel_push + metro_penalty)
            * self._bus_capacity_mult
        )
        auto = max(0.05, 0.12 + 0.06 * rain + jitter)

        total = walk + bike + car + metro + bus + auto
        share = {
            Mode.walk: walk / total,
            Mode.bike: bike / total,
            Mode.car: car / total,
            Mode.metro: metro / total,
            Mode.bus: bus / total,
            Mode.auto: auto / total,
        }

        base_commute = 28.0
        avg_commute = base_commute * (1 + 0.6 * rain + 0.5 * phase + 0.3 * metro_penalty)
        congestion = min(1.0, 0.2 + 0.5 * phase + 0.5 * rain + 0.2 * metro_penalty)
        metro_load = min(1.0, (0.3 + 0.5 * phase + 0.4 * rain + metro_penalty)) * 100
        commuting = int(self.config.population * phase)

        return AggregateMetrics(
            tick=self._tick,
            sim_time_minutes=self._tick * self.config.tick_minutes,
            rain_intensity=round(rain, 3),
            avg_commute_minutes=round(avg_commute, 2),
            mode_share={m: round(v, 4) for m, v in share.items()},
            metro_load_pct=round(metro_load, 2),
            road_congestion_index=round(congestion, 3),
            agents_commuting=commuting,
        )

    def _update_grid(self) -> None:
        phase = self._day_phase()
        for cell in self._cells:
            base = self._rng.uniform(0.0, 1.0)
            cell.density = int(self.config.population / len(self._cells) * (0.5 + phase) * base)
            cell.congestion = round(min(1.0, base * (0.3 + 0.6 * phase + 0.4 * self._rain)), 3)
