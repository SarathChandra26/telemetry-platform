"""app/domain/scenarios.py

Rule-based scenario detection for vehicle telemetry events.

Design goals:
  - Pure domain logic: zero I/O, zero framework dependencies.
  - Each rule is a first-class object — trivially testable in isolation.
  - New rules are added by appending a ScenarioRule to _REGISTRY.
  - Composite rules (e.g. risky_weather_event) are expressed as plain boolean
    composition of atomic predicates, keeping each predicate single-purpose.

Consumed by:
  app.services.telemetry → ingest pipeline
  app.repositories.telemetry → JSONB containment queries use these label strings
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Final, Optional, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Payload protocol
# Decoupled from the Pydantic schema so the engine works in any context:
# API ingestion, background workers, seed scripts, or plain unit tests.
# ---------------------------------------------------------------------------

@runtime_checkable
class ScenarioPayload(Protocol):
    """Structural interface for any object the scenario engine can evaluate."""

    speed: Decimal
    battery_level: int
    acceleration: Optional[Decimal]
    weather: Optional[str]
    engine_on: Optional[bool]  # noqa: F841 — used by congestion rule


# ---------------------------------------------------------------------------
# Atomic predicates
# Each is a plain function that returns bool.  Keep them pure and side-effect
# free so they can be composed safely without ordering concerns.
# ---------------------------------------------------------------------------

def _is_hard_brake(p: ScenarioPayload) -> bool:
    return p.acceleration is not None and p.acceleration < Decimal("-7")


def _is_rapid_acceleration(p: ScenarioPayload) -> bool:
    return p.acceleration is not None and p.acceleration > Decimal("7")


def _is_over_speeding(p: ScenarioPayload) -> bool:
    return p.speed > Decimal("100")


def _is_low_battery(p: ScenarioPayload) -> bool:
    return p.battery_level < 15


_RISKY_WEATHER_CONDITIONS: Final[frozenset[str]] = frozenset({"rain", "snow", "fog"})


def _is_risky_weather_event(p: ScenarioPayload) -> bool:
    """Composite: hard brake during adverse weather conditions."""
    return (
        _is_hard_brake(p)
        and p.weather is not None
        and p.weather.lower() in _RISKY_WEATHER_CONDITIONS
    )


# ---------------------------------------------------------------------------
# Rule dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ScenarioRule:
    """Immutable rule binding a label string to a predicate function.

    Args:
        label:     The scenario tag stored in JSONB and surfaced in API responses.
        predicate: Pure function (ScenarioPayload) → bool.
        description: Human-readable explanation for docs / admin dashboards.
    """

    label: str
    predicate: Callable[[ScenarioPayload], bool]
    description: str = ""

    def evaluate(self, payload: ScenarioPayload) -> bool:
        """Safely evaluate the predicate.  Missing optional fields → False."""
        try:
            return self.predicate(payload)
        except (TypeError, AttributeError):
            return False


# ---------------------------------------------------------------------------
# Rule registry
# Evaluation order is deterministic (tuple).  Composite rules (risky_weather)
# intentionally come last so atomic tags are always emitted first.
# ---------------------------------------------------------------------------

_REGISTRY: Final[tuple[ScenarioRule, ...]] = (
    ScenarioRule(
        label="hard_brake",
        predicate=_is_hard_brake,
        description="Deceleration below -7 m/s².",
    ),
    ScenarioRule(
        label="rapid_acceleration",
        predicate=_is_rapid_acceleration,
        description="Acceleration above +7 m/s².",
    ),
    ScenarioRule(
        label="over_speeding",
        predicate=_is_over_speeding,
        description="Speed exceeds 100 km/h.",
    ),
    ScenarioRule(
        label="low_battery",
        predicate=_is_low_battery,
        description="Battery level below 15%.",
    ),
    ScenarioRule(
        label="risky_weather_event",
        predicate=_is_risky_weather_event,
        description="Hard brake during rain, snow, or fog.",
    ),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_scenarios(payload: ScenarioPayload) -> list[str]:
    """Run all registered rules against *payload* and return fired labels.

    Labels are returned in registry declaration order.  The result is
    deduplicated — each label appears at most once.

    Example:
        >>> detect_scenarios(event)
        ["hard_brake", "risky_weather_event"]

    Args:
        payload: Any object satisfying the ScenarioPayload protocol.

    Returns:
        A (possibly empty) list of scenario label strings ready for JSONB storage.
    """
    seen: set[str] = set()
    result: list[str] = []
    for rule in _REGISTRY:
        if rule.evaluate(payload) and rule.label not in seen:
            seen.add(rule.label)
            result.append(rule.label)
    return result


def all_scenario_labels() -> frozenset[str]:
    """Return every possible scenario label defined in the registry.

    Used by:
      - API query param validation (fast reject of unknown scenario names)
      - OpenAPI schema enum generation
      - Test fixtures
    """
    return frozenset(rule.label for rule in _REGISTRY)


def get_rule_descriptions() -> dict[str, str]:
    """Return {label: description} for all registered rules.

    Useful for admin endpoints or auto-generated documentation.
    """
    return {rule.label: rule.description for rule in _REGISTRY}
