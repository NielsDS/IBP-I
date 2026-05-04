# Single-Echelon Safety Stock Calculator

State-of-the-art Python library and REST API for sizing safety stock and reorder points in a single-echelon inventory setting.

The implementation supports both common service objectives:

- `cycle_service_level` (probability of no stockout per replenishment cycle)
- `fill_rate` (fraction of demand immediately fulfilled from stock)

It includes:

- robust input validation with clear error messages
- explicit handling of demand and lead-time uncertainty
- continuous-review (`Q, R`) and periodic-review support via protection period
- **FastAPI REST API** with OpenAPI / Swagger docs
- CLI for batch scenario calculation
- Docker support for containerised deployments
- GitHub Actions CI (lint, type-check, tests, Docker build)
- comprehensive tests and examples

---

## Quick Start

### Library / CLI

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
safety-stock examples/scenarios.json --pretty
```

### REST API

```bash
pip install -e ".[api]"
safety-stock-api
# → API served at http://localhost:8000
# → OpenAPI docs at http://localhost:8000/docs
```

### Docker

```bash
docker compose up
# → API served at http://localhost:8000
```

---

## Input Fields

Each scenario requires:

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `sku` | string | ✓ | — | Unique scenario identifier |
| `mean_demand_per_period` | float > 0 | ✓ | — | Mean demand per period (μ_D) |
| `stdev_demand_per_period` | float ≥ 0 | ✓ | — | Demand std dev per period (σ_D) |
| `mean_lead_time_periods` | float > 0 | ✓ | — | Mean replenishment lead time (μ_L) |
| `stdev_lead_time_periods` | float ≥ 0 | | 0 | Lead-time std dev (σ_L) |
| `review_period_periods` | float ≥ 0 | | 0 | Review period (P); 0 = continuous review |
| `service_target_kind` | enum | ✓ | — | `cycle_service_level` or `fill_rate` |
| `service_target_value` | 0 < float < 1 | ✓ | — | Service level target |
| `order_quantity` | float > 0 | fill_rate only | — | Order quantity Q |

An example scenario payload is available at `examples/scenarios.json`.

---

## Mathematical Model

### Protection Period

The protection period is:

```
T = μ_L + P
```

Expected demand over the protection period:

```
E[D_T] = μ_D × T
```

Demand standard deviation over the protection period (independent demand and lead-time approximation):

```
σ_T = √(T × σ_D² + μ_D² × σ_L²)
```

### Cycle Service Level

Given target α:

```
z = Φ⁻¹(α)
SafetyStock = z × σ_T
ReorderPoint = E[D_T] + SafetyStock
```

### Fill Rate

Given target β and order quantity Q:

```
β ≈ 1 − E[Shortage] / Q
E[Shortage] = σ_T × L(z)
```

where `L(z)` is the unit normal loss function.

The calculator solves for `z` numerically, then computes safety stock and reorder point.

---

## REST API

The API is served with **FastAPI** and documented automatically via Swagger UI.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness / readiness probe |
| `POST` | `/calculate` | Calculate safety stock for one scenario |
| `POST` | `/calculate/batch` | Calculate safety stock for multiple scenarios |

### Example: single calculation

```bash
curl -s -X POST http://localhost:8000/calculate \
  -H 'Content-Type: application/json' \
  -d '{
    "sku": "SKU-A",
    "mean_demand_per_period": 120,
    "stdev_demand_per_period": 25,
    "mean_lead_time_periods": 2.5,
    "stdev_lead_time_periods": 0.6,
    "service_target_kind": "cycle_service_level",
    "service_target_value": 0.95
  }' | python -m json.tool
```

### Example: batch calculation

```bash
curl -s -X POST http://localhost:8000/calculate/batch \
  -H 'Content-Type: application/json' \
  -d '{"scenarios": [
    {
      "sku": "SKU-A",
      "mean_demand_per_period": 120,
      "stdev_demand_per_period": 25,
      "mean_lead_time_periods": 2.5,
      "service_target_kind": "cycle_service_level",
      "service_target_value": 0.95
    },
    {
      "sku": "SKU-B",
      "mean_demand_per_period": 80,
      "stdev_demand_per_period": 15,
      "mean_lead_time_periods": 3,
      "review_period_periods": 1,
      "service_target_kind": "fill_rate",
      "service_target_value": 0.98,
      "order_quantity": 400
    }
  ]}' | python -m json.tool
```

### Configuration (environment variables)

| Variable | Default | Description |
|---|---|---|
| `SS_HOST` | `0.0.0.0` | Bind address |
| `SS_PORT` | `8000` | Bind port |
| `SS_WORKERS` | `1` | Number of uvicorn worker processes |
| `SS_RELOAD` | `false` | Enable hot-reload (dev only) |
| `SS_LOG_LEVEL` | `INFO` | Logging level |
| `SS_LOG_JSON` | `false` | Emit JSON-formatted log lines |
| `SS_DOCS_ENABLED` | `true` | Expose `/docs` and `/redoc` |

---

## CLI Usage

```bash
safety-stock <input.json> [--pretty]
```

- `<input.json>` can contain one scenario object or a list of objects.
- `--pretty` pretty-prints the JSON output.

---

## Testing

```bash
pip install -e ".[api,dev]"
pytest
```

---

## Project Structure

```text
src/safety_stock/
    __init__.py          Public API exports
    models.py            Typed input/output models and validation
    calculator.py        Core formulas and numerical solve
    cli.py               Batch runner from JSON (console script)
    api.py               FastAPI REST API (console script: safety-stock-api)
    config.py            Environment-based runtime configuration
    logging_config.py    Structured logging setup
tests/
    test_calculator.py          Unit tests for core calculation logic
    test_validation_and_cli.py  Validation and CLI integration tests
    test_api.py                 REST API integration tests
examples/
    scenarios.json       Ready-to-run example scenarios
Dockerfile               Multi-stage production Docker image
docker-compose.yml       One-command local deployment
.github/workflows/ci.yml GitHub Actions CI (lint, typecheck, test, docker)
```

---

## Docker

```bash
# Build
docker build -t safety-stock-api .

# Run
docker run -p 8000:8000 safety-stock-api

# Or with Compose
docker compose up
```

---

## CI / CD

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push and pull request:

| Job | Description |
|---|---|
| `lint` | `ruff` lint + format check |
| `typecheck` | `mypy --strict` |
| `test` | `pytest` on Python 3.10, 3.11, and 3.12 |
| `docker` | Docker image build verification |
