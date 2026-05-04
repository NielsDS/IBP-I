from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .calculator import SafetyStockCalculator
from .models import DemandLeadTimeProfile, InputScenario, ServiceTarget


def _scenario_from_dict(raw: dict) -> InputScenario:
    profile = DemandLeadTimeProfile(
        mean_demand_per_period=float(raw["mean_demand_per_period"]),
        stdev_demand_per_period=float(raw["stdev_demand_per_period"]),
        mean_lead_time_periods=float(raw["mean_lead_time_periods"]),
        stdev_lead_time_periods=float(raw.get("stdev_lead_time_periods", 0.0)),
        review_period_periods=float(raw.get("review_period_periods", 0.0)),
    )

    target = ServiceTarget(
        kind=raw["service_target_kind"],
        value=float(raw["service_target_value"]),
        order_quantity=(
            float(raw["order_quantity"]) if "order_quantity" in raw else None
        ),
    )

    return InputScenario(sku=str(raw["sku"]), profile=profile, target=target)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Single-echelon safety stock calculator"
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="Path to JSON file with one scenario object or a list of scenario objects",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = json.loads(args.input_file.read_text(encoding="utf-8"))

    raw_items = raw if isinstance(raw, list) else [raw]
    scenarios = [_scenario_from_dict(item) for item in raw_items]

    calculator = SafetyStockCalculator()
    results = [asdict(calculator.calculate(s)) for s in scenarios]

    if args.pretty:
        print(json.dumps(results, indent=2))
    else:
        print(json.dumps(results))


if __name__ == "__main__":
    main()
