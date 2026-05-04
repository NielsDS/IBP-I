from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

ServiceTargetKind = Literal["cycle_service_level", "fill_rate"]


@dataclass(frozen=True)
class DemandLeadTimeProfile:
    """Inputs that characterize demand and lead time uncertainty."""

    mean_demand_per_period: float
    stdev_demand_per_period: float
    mean_lead_time_periods: float
    stdev_lead_time_periods: float = 0.0
    review_period_periods: float = 0.0

    def validate(self) -> None:
        if self.mean_demand_per_period <= 0:
            raise ValueError("mean_demand_per_period must be > 0")
        if self.stdev_demand_per_period < 0:
            raise ValueError("stdev_demand_per_period must be >= 0")
        if self.mean_lead_time_periods <= 0:
            raise ValueError("mean_lead_time_periods must be > 0")
        if self.stdev_lead_time_periods < 0:
            raise ValueError("stdev_lead_time_periods must be >= 0")
        if self.review_period_periods < 0:
            raise ValueError("review_period_periods must be >= 0")


@dataclass(frozen=True)
class ServiceTarget:
    """Service objective for inventory policy sizing."""

    kind: ServiceTargetKind
    value: float
    order_quantity: Optional[float] = None

    def validate(self) -> None:
        if not (0 < self.value < 1):
            raise ValueError("Service target value must be between 0 and 1")
        if self.kind == "fill_rate":
            if self.order_quantity is None or self.order_quantity <= 0:
                raise ValueError("fill_rate target requires order_quantity > 0")


@dataclass(frozen=True)
class InputScenario:
    """Complete scenario description for a single SKU/location."""

    sku: str
    profile: DemandLeadTimeProfile
    target: ServiceTarget

    def validate(self) -> None:
        if not self.sku.strip():
            raise ValueError("sku must not be empty")
        self.profile.validate()
        self.target.validate()


@dataclass(frozen=True)
class CalculationResult:
    sku: str
    target_kind: ServiceTargetKind
    target_value: float
    z_value: float
    expected_demand_in_protection_period: float
    stdev_demand_in_protection_period: float
    safety_stock: float
    reorder_point: float
    expected_shortage_per_cycle: Optional[float] = None
