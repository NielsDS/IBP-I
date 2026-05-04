"""Integration tests for the FastAPI REST API."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from safety_stock.api import create_app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(), raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert "version" in resp.json()


# ---------------------------------------------------------------------------
# POST /calculate – happy paths
# ---------------------------------------------------------------------------

def test_calculate_cycle_service_level(client: TestClient) -> None:
    payload = {
        "sku": "TEST-1",
        "mean_demand_per_period": 100,
        "stdev_demand_per_period": 20,
        "mean_lead_time_periods": 2,
        "stdev_lead_time_periods": 0.5,
        "service_target_kind": "cycle_service_level",
        "service_target_value": 0.95,
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sku"] == "TEST-1"
    assert data["safety_stock"] > 0
    assert data["reorder_point"] > data["expected_demand_in_protection_period"]
    assert data["expected_shortage_per_cycle"] is None


def test_calculate_fill_rate(client: TestClient) -> None:
    payload = {
        "sku": "TEST-2",
        "mean_demand_per_period": 50,
        "stdev_demand_per_period": 10,
        "mean_lead_time_periods": 3,
        "stdev_lead_time_periods": 1,
        "service_target_kind": "fill_rate",
        "service_target_value": 0.98,
        "order_quantity": 250,
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["expected_shortage_per_cycle"] is not None
    assert data["safety_stock"] > 0


def test_calculate_deterministic_zero_safety_stock(client: TestClient) -> None:
    payload = {
        "sku": "TEST-DET",
        "mean_demand_per_period": 50,
        "stdev_demand_per_period": 0,
        "mean_lead_time_periods": 3,
        "stdev_lead_time_periods": 0,
        "service_target_kind": "cycle_service_level",
        "service_target_value": 0.9,
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["safety_stock"] == 0.0
    assert data["reorder_point"] == pytest.approx(150.0)


def test_calculate_with_review_period(client: TestClient) -> None:
    payload = {
        "sku": "TEST-REV",
        "mean_demand_per_period": 80,
        "stdev_demand_per_period": 15,
        "mean_lead_time_periods": 2,
        "stdev_lead_time_periods": 0.3,
        "review_period_periods": 1,
        "service_target_kind": "cycle_service_level",
        "service_target_value": 0.9,
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    # Protection period = mean_lead_time + review_period = 3 periods
    assert data["expected_demand_in_protection_period"] == pytest.approx(240.0)


# ---------------------------------------------------------------------------
# POST /calculate – validation errors
# ---------------------------------------------------------------------------

def test_calculate_rejects_missing_sku(client: TestClient) -> None:
    payload = {
        "mean_demand_per_period": 100,
        "stdev_demand_per_period": 20,
        "mean_lead_time_periods": 2,
        "service_target_kind": "cycle_service_level",
        "service_target_value": 0.95,
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 422


def test_calculate_rejects_negative_demand(client: TestClient) -> None:
    payload = {
        "sku": "BAD",
        "mean_demand_per_period": -5,
        "stdev_demand_per_period": 0,
        "mean_lead_time_periods": 2,
        "service_target_kind": "cycle_service_level",
        "service_target_value": 0.95,
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 422


def test_calculate_rejects_service_value_out_of_bounds(client: TestClient) -> None:
    payload = {
        "sku": "BAD",
        "mean_demand_per_period": 100,
        "stdev_demand_per_period": 10,
        "mean_lead_time_periods": 2,
        "service_target_kind": "cycle_service_level",
        "service_target_value": 1.5,
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 422


def test_calculate_rejects_fill_rate_without_order_quantity(client: TestClient) -> None:
    payload = {
        "sku": "BAD",
        "mean_demand_per_period": 100,
        "stdev_demand_per_period": 10,
        "mean_lead_time_periods": 2,
        "service_target_kind": "fill_rate",
        "service_target_value": 0.95,
        # order_quantity intentionally omitted
    }
    resp = client.post("/calculate", json=payload)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /calculate/batch – happy paths
# ---------------------------------------------------------------------------

def test_batch_calculate(client: TestClient) -> None:
    payload = {
        "scenarios": [
            {
                "sku": "BATCH-1",
                "mean_demand_per_period": 100,
                "stdev_demand_per_period": 20,
                "mean_lead_time_periods": 2,
                "service_target_kind": "cycle_service_level",
                "service_target_value": 0.95,
            },
            {
                "sku": "BATCH-2",
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
    }
    resp = client.post("/calculate/batch", json=payload)
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 2
    assert {r["sku"] for r in results} == {"BATCH-1", "BATCH-2"}


def test_batch_returns_422_on_any_invalid_scenario(client: TestClient) -> None:
    payload = {
        "scenarios": [
            {
                "sku": "GOOD",
                "mean_demand_per_period": 100,
                "stdev_demand_per_period": 10,
                "mean_lead_time_periods": 2,
                "service_target_kind": "cycle_service_level",
                "service_target_value": 0.95,
            },
            {
                # invalid: fill_rate without order_quantity
                "sku": "BAD",
                "mean_demand_per_period": 100,
                "stdev_demand_per_period": 10,
                "mean_lead_time_periods": 2,
                "service_target_kind": "fill_rate",
                "service_target_value": 0.95,
            },
        ]
    }
    resp = client.post("/calculate/batch", json=payload)
    assert resp.status_code == 422


def test_batch_rejects_empty_scenarios(client: TestClient) -> None:
    payload = {"scenarios": []}
    resp = client.post("/calculate/batch", json=payload)
    assert resp.status_code == 422
