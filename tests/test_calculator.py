from safety_stock.calculator import SafetyStockCalculator
from safety_stock.models import DemandLeadTimeProfile, InputScenario, ServiceTarget


def test_cycle_service_level_reorder_point_above_mean() -> None:
    calc = SafetyStockCalculator()
    scenario = InputScenario(
        sku="SKU-1",
        profile=DemandLeadTimeProfile(
            mean_demand_per_period=100,
            stdev_demand_per_period=20,
            mean_lead_time_periods=2,
            stdev_lead_time_periods=0.5,
        ),
        target=ServiceTarget(kind="cycle_service_level", value=0.95),
    )

    result = calc.calculate(scenario)

    assert result.safety_stock > 0
    assert result.reorder_point > result.expected_demand_in_protection_period


def test_fill_rate_uses_expected_shortage() -> None:
    calc = SafetyStockCalculator()
    scenario = InputScenario(
        sku="SKU-2",
        profile=DemandLeadTimeProfile(
            mean_demand_per_period=50,
            stdev_demand_per_period=10,
            mean_lead_time_periods=3,
            stdev_lead_time_periods=1,
        ),
        target=ServiceTarget(kind="fill_rate", value=0.98, order_quantity=250),
    )

    result = calc.calculate(scenario)

    assert result.expected_shortage_per_cycle is not None
    assert result.expected_shortage_per_cycle <= 5.1


def test_deterministic_case_has_zero_safety_stock() -> None:
    calc = SafetyStockCalculator()
    scenario = InputScenario(
        sku="SKU-3",
        profile=DemandLeadTimeProfile(
            mean_demand_per_period=50,
            stdev_demand_per_period=0,
            mean_lead_time_periods=3,
            stdev_lead_time_periods=0,
        ),
        target=ServiceTarget(kind="cycle_service_level", value=0.9),
    )

    result = calc.calculate(scenario)

    assert result.safety_stock == 0
    assert result.reorder_point == 150
