"""tests/unit/test_domain_scenarios.py

Unit tests for the domain scenario detection engine.

Pure unit tests — zero I/O, zero async, no fixtures needed.
Uses a minimal stub that satisfies the ScenarioPayload Protocol.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import pytest

from app.domain.scenarios import (
    ScenarioRule,
    all_scenario_labels,
    detect_scenarios,
    get_rule_descriptions,
)


# ---------------------------------------------------------------------------
# Minimal payload stub — satisfies ScenarioPayload Protocol without Pydantic
# ---------------------------------------------------------------------------

@dataclass
class _Event:
    speed: Decimal
    battery_level: int
    acceleration: Optional[Decimal] = None
    weather: Optional[str] = None
    engine_on: Optional[bool] = None


def ev(
    speed: float = 60.0,
    battery: int = 80,
    accel: Optional[float] = None,
    weather: Optional[str] = None,
    engine_on: Optional[bool] = None,
) -> _Event:
    """Convenience factory — keeps test bodies concise."""
    return _Event(
        speed=Decimal(str(speed)),
        battery_level=battery,
        acceleration=Decimal(str(accel)) if accel is not None else None,
        weather=weather,
        engine_on=engine_on,
    )


# ---------------------------------------------------------------------------
# Nominal — no scenarios
# ---------------------------------------------------------------------------

class TestNominalEvent:
    def test_normal_driving_produces_no_scenarios(self) -> None:
        assert detect_scenarios(ev(speed=60, battery=80, accel=-2.0)) == []

    def test_no_optional_fields_produces_no_scenarios(self) -> None:
        assert detect_scenarios(ev()) == []


# ---------------------------------------------------------------------------
# hard_brake  (acceleration < -7)
# ---------------------------------------------------------------------------

class TestHardBrake:
    def test_fires_when_acceleration_below_minus_seven(self) -> None:
        assert "hard_brake" in detect_scenarios(ev(accel=-7.1))

    def test_boundary_at_minus_seven_does_not_fire(self) -> None:
        # Strict < -7, so exactly -7.0 must NOT trigger
        assert "hard_brake" not in detect_scenarios(ev(accel=-7.0))

    def test_does_not_fire_without_acceleration_field(self) -> None:
        assert "hard_brake" not in detect_scenarios(ev())

    def test_does_not_fire_for_moderate_deceleration(self) -> None:
        assert "hard_brake" not in detect_scenarios(ev(accel=-3.0))


# ---------------------------------------------------------------------------
# rapid_acceleration  (acceleration > 7)
# ---------------------------------------------------------------------------

class TestRapidAcceleration:
    def test_fires_above_seven(self) -> None:
        assert "rapid_acceleration" in detect_scenarios(ev(accel=7.5))

    def test_boundary_at_seven_does_not_fire(self) -> None:
        assert "rapid_acceleration" not in detect_scenarios(ev(accel=7.0))

    def test_does_not_fire_for_moderate_acceleration(self) -> None:
        assert "rapid_acceleration" not in detect_scenarios(ev(accel=4.0))

    def test_does_not_fire_without_acceleration(self) -> None:
        assert "rapid_acceleration" not in detect_scenarios(ev())


# ---------------------------------------------------------------------------
# over_speeding  (speed > 100)
# ---------------------------------------------------------------------------

class TestOverSpeeding:
    def test_fires_above_100(self) -> None:
        assert "over_speeding" in detect_scenarios(ev(speed=101.0))

    def test_boundary_at_100_does_not_fire(self) -> None:
        assert "over_speeding" not in detect_scenarios(ev(speed=100.0))

    def test_does_not_fire_below_100(self) -> None:
        assert "over_speeding" not in detect_scenarios(ev(speed=90.0))


# ---------------------------------------------------------------------------
# low_battery  (battery_level < 15)
# ---------------------------------------------------------------------------

class TestLowBattery:
    def test_fires_below_15(self) -> None:
        assert "low_battery" in detect_scenarios(ev(battery=14))

    def test_boundary_at_15_does_not_fire(self) -> None:
        assert "low_battery" not in detect_scenarios(ev(battery=15))

    def test_does_not_fire_above_15(self) -> None:
        assert "low_battery" not in detect_scenarios(ev(battery=50))


# ---------------------------------------------------------------------------
# risky_weather_event  (hard_brake AND weather in {rain, snow, fog})
# ---------------------------------------------------------------------------

class TestRiskyWeatherEvent:
    @pytest.mark.parametrize("weather", ["rain", "snow", "fog", "Rain", "SNOW", "Fog"])
    def test_fires_for_all_adverse_weather_with_hard_brake(self, weather: str) -> None:
        result = detect_scenarios(ev(accel=-8.0, weather=weather))
        assert "risky_weather_event" in result

    def test_does_not_fire_for_clear_weather(self) -> None:
        result = detect_scenarios(ev(accel=-8.0, weather="clear"))
        assert "risky_weather_event" not in result

    def test_does_not_fire_without_hard_brake(self) -> None:
        result = detect_scenarios(ev(accel=-3.0, weather="rain"))
        assert "risky_weather_event" not in result

    def test_does_not_fire_without_weather_field(self) -> None:
        result = detect_scenarios(ev(accel=-8.0))
        assert "risky_weather_event" not in result

    def test_fires_alongside_hard_brake_label(self) -> None:
        """risky_weather_event is composite — hard_brake must also be present."""
        result = detect_scenarios(ev(accel=-8.0, weather="snow"))
        assert "hard_brake" in result
        assert "risky_weather_event" in result


# ---------------------------------------------------------------------------
# Multi-label co-occurrence
# ---------------------------------------------------------------------------

class TestMultiLabel:
    def test_hard_brake_and_over_speeding_can_co_occur(self) -> None:
        result = detect_scenarios(ev(speed=120.0, accel=-8.0))
        assert "hard_brake" in result
        assert "over_speeding" in result

    def test_all_five_labels_at_once(self) -> None:
        result = detect_scenarios(
            ev(speed=120.0, battery=10, accel=-8.0, weather="rain")
        )
        assert set(result) >= {
            "hard_brake",
            "over_speeding",
            "low_battery",
            "risky_weather_event",
        }

    def test_result_contains_no_duplicates(self) -> None:
        result = detect_scenarios(ev(speed=120.0, battery=5, accel=-8.0, weather="snow"))
        assert len(result) == len(set(result))

    def test_rapid_acceleration_and_over_speeding(self) -> None:
        result = detect_scenarios(ev(speed=110.0, accel=8.5))
        assert "rapid_acceleration" in result
        assert "over_speeding" in result


# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------

class TestRegistry:
    def test_all_scenario_labels_returns_all_five(self) -> None:
        labels = all_scenario_labels()
        assert labels == {
            "hard_brake",
            "rapid_acceleration",
            "over_speeding",
            "low_battery",
            "risky_weather_event",
        }

    def test_returns_frozenset(self) -> None:
        assert isinstance(all_scenario_labels(), frozenset)

    def test_get_rule_descriptions_has_entry_for_every_label(self) -> None:
        descs = get_rule_descriptions()
        assert set(descs.keys()) == all_scenario_labels()
        assert all(isinstance(v, str) and v for v in descs.values())


# ---------------------------------------------------------------------------
# ScenarioRule.evaluate defensive behaviour
# ---------------------------------------------------------------------------

class TestScenarioRuleEvaluate:
    def test_evaluate_returns_false_on_attribute_error(self) -> None:
        """Predicate referencing a missing attribute must not raise."""

        class BadPayload:
            speed = Decimal("60")
            battery_level = 50
            # acceleration, weather, engine_on intentionally omitted

        rule = ScenarioRule(
            label="test",
            predicate=lambda p: p.missing_field > 0,  # type: ignore[attr-defined]
        )
        assert rule.evaluate(BadPayload()) is False  # type: ignore[arg-type]

    def test_evaluate_returns_false_on_type_error(self) -> None:
        rule = ScenarioRule(
            label="test",
            predicate=lambda p: None > 0,  # type: ignore[operator]
        )
        assert rule.evaluate(ev()) is False
