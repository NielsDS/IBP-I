"""FastAPI REST API for the single-echelon safety stock calculator.

Endpoints
---------
GET  /health          Liveness / readiness probe.
POST /calculate       Compute safety stock for one scenario.
POST /calculate/batch Compute safety stock for multiple scenarios.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator, Literal, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

from .calculator import SafetyStockCalculator
from .config import settings
from .logging_config import configure_logging
from .models import (
    CalculationResult,
    DemandLeadTimeProfile,
    InputScenario,
    ServiceTarget,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------

ServiceTargetKindEnum = Literal["cycle_service_level", "fill_rate"]


class ScenarioRequest(BaseModel):
    """JSON body for a single safety-stock calculation."""

    sku: Annotated[str, Field(min_length=1, description="Unique SKU/scenario identifier")]
    mean_demand_per_period: Annotated[
        float, Field(gt=0, description="Mean demand per time period (μ_D)")
    ]
    stdev_demand_per_period: Annotated[
        float, Field(ge=0, description="Standard deviation of demand per period (σ_D)")
    ]
    mean_lead_time_periods: Annotated[
        float, Field(gt=0, description="Mean replenishment lead time in periods (μ_L)")
    ]
    stdev_lead_time_periods: Annotated[
        float, Field(ge=0, description="Standard deviation of lead time (σ_L)")
    ] = 0.0
    review_period_periods: Annotated[
        float,
        Field(ge=0, description="Review period length in periods (P). 0 = continuous review"),
    ] = 0.0
    service_target_kind: ServiceTargetKindEnum
    service_target_value: Annotated[
        float, Field(gt=0, lt=1, description="Target service level (exclusive of 0 and 1)")
    ]
    order_quantity: Annotated[
        Optional[float],
        Field(gt=0, description="Order quantity Q – required when service_target_kind=fill_rate"),
    ] = None

    @model_validator(mode="after")
    def _fill_rate_requires_order_quantity(self) -> "ScenarioRequest":
        if self.service_target_kind == "fill_rate" and (
            self.order_quantity is None or self.order_quantity <= 0
        ):
            raise ValueError("order_quantity > 0 is required when service_target_kind=fill_rate")
        return self


class BatchRequest(BaseModel):
    """JSON body for a batch calculation."""

    scenarios: Annotated[
        list[ScenarioRequest], Field(min_length=1, description="List of scenarios to evaluate")
    ]


class ResultResponse(BaseModel):
    """JSON response for a single calculation result."""

    sku: str
    target_kind: str
    target_value: float
    z_value: float
    expected_demand_in_protection_period: float
    stdev_demand_in_protection_period: float
    safety_stock: float
    reorder_point: float
    expected_shortage_per_cycle: Optional[float] = None

    @classmethod
    def from_result(cls, r: CalculationResult) -> "ResultResponse":
        return cls(
            sku=r.sku,
            target_kind=r.target_kind,
            target_value=r.target_value,
            z_value=r.z_value,
            expected_demand_in_protection_period=r.expected_demand_in_protection_period,
            stdev_demand_in_protection_period=r.stdev_demand_in_protection_period,
            safety_stock=r.safety_stock,
            reorder_point=r.reorder_point,
            expected_shortage_per_cycle=r.expected_shortage_per_cycle,
        )


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = "0.1.0"


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def _build_input_scenario(req: ScenarioRequest) -> InputScenario:
    profile = DemandLeadTimeProfile(
        mean_demand_per_period=req.mean_demand_per_period,
        stdev_demand_per_period=req.stdev_demand_per_period,
        mean_lead_time_periods=req.mean_lead_time_periods,
        stdev_lead_time_periods=req.stdev_lead_time_periods,
        review_period_periods=req.review_period_periods,
    )
    target = ServiceTarget(
        kind=req.service_target_kind,
        value=req.service_target_value,
        order_quantity=req.order_quantity,
    )
    return InputScenario(sku=req.sku, profile=profile, target=target)


def create_app() -> FastAPI:
    """Create and return the configured FastAPI application."""
    docs_kwargs: dict = (
        {}
        if settings.docs_enabled
        else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    )

    calculator = SafetyStockCalculator()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        configure_logging(level=settings.log_level, json_logs=settings.log_json)
        logger.info("Safety-stock API started (log_level=%s)", settings.log_level)
        yield
        logger.info("Safety-stock API shut down")

    app = FastAPI(
        title="Single-Echelon Safety Stock API",
        description=(
            "Computes safety stock and reorder points for single-echelon inventory systems "
            "supporting both *cycle service level* and *fill rate* objectives."
        ),
        version="0.1.0",
        lifespan=lifespan,
        **docs_kwargs,
    )

    # -----------------------------------------------------------------------
    # Exception handlers
    # -----------------------------------------------------------------------

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
        logger.warning("Validation error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": str(exc)},
        )

    # -----------------------------------------------------------------------
    # Routes
    # -----------------------------------------------------------------------

    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["ops"],
        summary="Liveness/readiness probe",
    )
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.post(
        "/calculate",
        response_model=ResultResponse,
        tags=["calculator"],
        summary="Calculate safety stock for a single SKU scenario",
        status_code=status.HTTP_200_OK,
    )
    async def calculate(body: ScenarioRequest) -> ResultResponse:
        logger.debug("Calculating scenario sku=%s", body.sku)
        try:
            scenario = _build_input_scenario(body)
            result = calculator.calculate(scenario)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        return ResultResponse.from_result(result)

    @app.post(
        "/calculate/batch",
        response_model=list[ResultResponse],
        tags=["calculator"],
        summary="Calculate safety stock for multiple SKU scenarios",
        status_code=status.HTTP_200_OK,
    )
    async def calculate_batch(body: BatchRequest) -> list[ResultResponse]:
        logger.debug("Batch calculation: %d scenarios", len(body.scenarios))
        results: list[ResultResponse] = []
        errors: list[str] = []
        for req in body.scenarios:
            try:
                scenario = _build_input_scenario(req)
                result = calculator.calculate(scenario)
                results.append(ResultResponse.from_result(result))
            except ValueError as exc:
                errors.append(f"SKU '{req.sku}': {exc}")

        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=errors,
            )
        return results

    return app


# Module-level app instance used by uvicorn and tests.
app = create_app()


def run() -> None:
    """Entry-point for the ``safety-stock-api`` console script."""
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    uvicorn.run(
        "safety_stock.api:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers,
        reload=settings.reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
