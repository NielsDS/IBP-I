"""Tests for input validation on models and the CLI."""
from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

from safety_stock.cli import main
from safety_stock.models import DemandLeadTimeProfile, InputScenario, ServiceTarget


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestDemandLeadTimeProfileValidation:
    def test_zero_mean_demand_raises(self) -> None:
        profile = DemandLeadTimeProfile(
            mean_demand_per_period=0,
            stdev_demand_per_period=5,
            mean_lead_time_periods=2,
        )
        with pytest.raises(ValueError, match="mean_demand_per_period"):
            profile.validate()

    def test_negative_stdev_demand_raises(self) -> None:
        profile = DemandLeadTimeProfile(
            mean_demand_per_period=10,
            stdev_demand_per_period=-1,
            mean_lead_time_periods=2,
        )
        with pytest.raises(ValueError, match="stdev_demand_per_period"):
            profile.validate()

    def test_zero_lead_time_raises(self) -> None:
        profile = DemandLeadTimeProfile(
            mean_demand_per_period=10,
            stdev_demand_per_period=2,
            mean_lead_time_periods=0,
        )
        with pytest.raises(ValueError, match="mean_lead_time_periods"):
            profile.validate()

    def test_negative_stdev_lead_time_raises(self) -> None:
        profile = DemandLeadTimeProfile(
            mean_demand_per_period=10,
            stdev_demand_per_period=2,
            mean_lead_time_periods=2,
            stdev_lead_time_periods=-0.1,
        )
        with pytest.raises(ValueError, match="stdev_lead_time_periods"):
            profile.validate()

    def test_negative_review_period_raises(self) -> None:
        profile = DemandLeadTimeProfile(
            mean_demand_per_period=10,
            stdev_demand_per_period=2,
            mean_lead_time_periods=2,
            review_period_periods=-1,
        )
        with pytest.raises(ValueError, match="review_period_periods"):
            profile.validate()

    def test_valid_profile_does_not_raise(self) -> None:
        profile = DemandLeadTimeProfile(
            mean_demand_per_period=100,
            stdev_demand_per_period=10,
            mean_lead_time_periods=2,
            stdev_lead_time_periods=0.5,
            review_period_periods=1,
        )
        profile.validate()  # should not raise


class TestServiceTargetValidation:
    def test_zero_value_raises(self) -> None:
        t = ServiceTarget(kind="cycle_service_level", value=0)
        with pytest.raises(ValueError):
            t.validate()

    def test_one_value_raises(self) -> None:
        t = ServiceTarget(kind="cycle_service_level", value=1)
        with pytest.raises(ValueError):
            t.validate()

    def test_fill_rate_without_order_quantity_raises(self) -> None:
        t = ServiceTarget(kind="fill_rate", value=0.95)
        with pytest.raises(ValueError, match="order_quantity"):
            t.validate()

    def test_fill_rate_with_zero_order_quantity_raises(self) -> None:
        t = ServiceTarget(kind="fill_rate", value=0.95, order_quantity=0)
        with pytest.raises(ValueError, match="order_quantity"):
            t.validate()

    def test_fill_rate_with_order_quantity_is_valid(self) -> None:
        t = ServiceTarget(kind="fill_rate", value=0.95, order_quantity=100)
        t.validate()  # should not raise


class TestInputScenarioValidation:
    def test_empty_sku_raises(self) -> None:
        scenario = InputScenario(
            sku="   ",
            profile=DemandLeadTimeProfile(
                mean_demand_per_period=100,
                stdev_demand_per_period=10,
                mean_lead_time_periods=2,
            ),
            target=ServiceTarget(kind="cycle_service_level", value=0.95),
        )
        with pytest.raises(ValueError, match="sku"):
            scenario.validate()


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------


class TestCLI:
    def test_cli_single_scenario(self, tmp_path: Path) -> None:
        scenario = {
            "sku": "CLI-1",
            "mean_demand_per_period": 100,
            "stdev_demand_per_period": 20,
            "mean_lead_time_periods": 2,
            "stdev_lead_time_periods": 0.5,
            "service_target_kind": "cycle_service_level",
            "service_target_value": 0.95,
        }
        input_file = tmp_path / "scenario.json"
        input_file.write_text(json.dumps(scenario))

        captured = StringIO()
        with patch("sys.argv", ["safety-stock", str(input_file)]):
            with patch("sys.stdout", captured):
                main()

        results = json.loads(captured.getvalue())
        assert isinstance(results, list)
        assert results[0]["sku"] == "CLI-1"
        assert results[0]["safety_stock"] > 0

    def test_cli_batch_scenarios(self, tmp_path: Path) -> None:
        scenarios = [
            {
                "sku": "CLI-A",
                "mean_demand_per_period": 120,
                "stdev_demand_per_period": 25,
                "mean_lead_time_periods": 2.5,
                "stdev_lead_time_periods": 0.6,
                "service_target_kind": "cycle_service_level",
                "service_target_value": 0.95,
            },
            {
                "sku": "CLI-B",
                "mean_demand_per_period": 80,
                "stdev_demand_per_period": 15,
                "mean_lead_time_periods": 3,
                "stdev_lead_time_periods": 0.8,
                "review_period_periods": 1,
                "service_target_kind": "fill_rate",
                "service_target_value": 0.98,
                "order_quantity": 400,
            },
        ]
        input_file = tmp_path / "scenarios.json"
        input_file.write_text(json.dumps(scenarios))

        captured = StringIO()
        with patch("sys.argv", ["safety-stock", str(input_file)]):
            with patch("sys.stdout", captured):
                main()

        results = json.loads(captured.getvalue())
        assert len(results) == 2

    def test_cli_pretty_flag(self, tmp_path: Path) -> None:
        scenario = {
            "sku": "PRETTY",
            "mean_demand_per_period": 50,
            "stdev_demand_per_period": 5,
            "mean_lead_time_periods": 1,
            "service_target_kind": "cycle_service_level",
            "service_target_value": 0.9,
        }
        input_file = tmp_path / "s.json"
        input_file.write_text(json.dumps(scenario))

        captured = StringIO()
        with patch("sys.argv", ["safety-stock", str(input_file), "--pretty"]):
            with patch("sys.stdout", captured):
                main()

        output = captured.getvalue()
        # Pretty-printed JSON has indentation
        assert "\n" in output
        results = json.loads(output)
        assert results[0]["sku"] == "PRETTY"
