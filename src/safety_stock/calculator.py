from __future__ import annotations

import math
from dataclasses import asdict
from statistics import NormalDist

from .models import CalculationResult, InputScenario


class SafetyStockCalculator:
    """Computes safety stock and reorder point for single-echelon inventory."""

    _normal = NormalDist(mu=0.0, sigma=1.0)

    def calculate(self, scenario: InputScenario) -> CalculationResult:
        scenario.validate()

        mean_pp = self._protection_period_mean(scenario)
        stdev_pp = self._protection_period_stdev(scenario)
        target = scenario.target

        if stdev_pp == 0:
            # Deterministic case: no uncertainty, no safety stock required.
            z_value = 0.0
            safety_stock = 0.0
            expected_shortage = 0.0 if target.kind == "fill_rate" else None
        elif target.kind == "cycle_service_level":
            z_value = self._normal.inv_cdf(target.value)
            safety_stock = z_value * stdev_pp
            expected_shortage = None
        else:
            order_qty = float(target.order_quantity)
            z_value = self._solve_z_for_fill_rate(target.value, order_qty, stdev_pp)
            safety_stock = z_value * stdev_pp
            expected_shortage = self._expected_shortage_per_cycle(z_value, stdev_pp)

        reorder_point = mean_pp + safety_stock

        return CalculationResult(
            sku=scenario.sku,
            target_kind=target.kind,
            target_value=target.value,
            z_value=z_value,
            expected_demand_in_protection_period=mean_pp,
            stdev_demand_in_protection_period=stdev_pp,
            safety_stock=safety_stock,
            reorder_point=reorder_point,
            expected_shortage_per_cycle=expected_shortage,
        )

    def as_dict(self, scenario: InputScenario) -> dict[str, float | str | None]:
        return asdict(self.calculate(scenario))

    @staticmethod
    def _protection_period_mean(scenario: InputScenario) -> float:
        p = scenario.profile
        return p.mean_demand_per_period * (p.mean_lead_time_periods + p.review_period_periods)

    @staticmethod
    def _protection_period_stdev(scenario: InputScenario) -> float:
        p = scenario.profile
        protection_window = p.mean_lead_time_periods + p.review_period_periods

        if protection_window <= 0:
            raise ValueError("Protection period must be > 0")

        demand_component = protection_window * (p.stdev_demand_per_period ** 2)
        lead_time_component = (p.mean_demand_per_period ** 2) * (p.stdev_lead_time_periods ** 2)
        variance = demand_component + lead_time_component

        if variance < 0:
            raise ValueError("Computed variance is negative, check inputs")

        return math.sqrt(variance)

    def _solve_z_for_fill_rate(self, fill_rate: float, order_qty: float, sigma_pp: float) -> float:
        # Fill rate beta ~= 1 - E[shortage]/Q. We invert this numerically.
        target_shortage = (1 - fill_rate) * order_qty

        lo, hi = -4.0, 8.0
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            shortage = self._expected_shortage_per_cycle(mid, sigma_pp)
            if shortage > target_shortage:
                lo = mid
            else:
                hi = mid

        return 0.5 * (lo + hi)

    def _expected_shortage_per_cycle(self, z_value: float, sigma_pp: float) -> float:
        cdf = self._normal.cdf(z_value)
        pdf = self._normal.pdf(z_value)
        # Unit normal loss function: L(z) = phi(z) - z * (1 - Phi(z))
        loss = pdf - z_value * (1 - cdf)
        return sigma_pp * loss
