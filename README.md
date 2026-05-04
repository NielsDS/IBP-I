# Single-Echelon Safety Stock Calculator

State-of-the-art Python calculator for sizing safety stock and reorder points in a single-echelon inventory setting.

The implementation supports both common service objectives:

- `cycle_service_level` (probability of no stockout per replenishment cycle)
- `fill_rate` (fraction of demand immediately fulfilled from stock)

It includes:

- robust input validation
- explicit handling of demand and lead-time uncertainty
- continuous-review (`Q, R`) and periodic-review support via protection period
- CLI for batch scenario calculation
- tests and examples

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
safety-stock examples/scenarios.json --pretty
```

## Input Fields

Each scenario requires:

- `sku`: scenario identifier
- `mean_demand_per_period` (`mu_D`)
- `stdev_demand_per_period` (`sigma_D`)
- `mean_lead_time_periods` (`mu_L`)
- `stdev_lead_time_periods` (`sigma_L`, optional, default `0`)
- `review_period_periods` (`P`, optional, default `0`)
- `service_target_kind`: `cycle_service_level` or `fill_rate`
- `service_target_value`: target between `0` and `1`
- `order_quantity`: required only for `fill_rate`

Example scenario payload is available at `examples/scenarios.json`.

## Mathematical Model

### Protection Period

The protection period is:

`T = mu_L + P`

Expected demand over protection period:

`E[D_T] = mu_D * T`

Demand standard deviation over protection period (independent demand and lead-time approximation):

`sigma_T = sqrt(T * sigma_D^2 + mu_D^2 * sigma_L^2)`

### Cycle Service Level

Given target `alpha`:

`z = Phi^-1(alpha)`

`SafetyStock = z * sigma_T`

`ReorderPoint = E[D_T] + SafetyStock`

### Fill Rate

Given target `beta` and order quantity `Q`:

`beta ~= 1 - E[Shortage] / Q`

`E[Shortage] = sigma_T * L(z)`

where `L(z)` is the unit normal loss function.

The calculator solves for `z` numerically, then computes safety stock and reorder point.

## CLI Usage

```bash
safety-stock <input.json> [--pretty]
```

- `<input.json>` can contain one scenario object or a list of objects.

## Testing

```bash
pip install -e .[dev]
pytest
```

## Project Structure

```text
src/safety_stock/models.py      # Typed input/output models and validation
src/safety_stock/calculator.py  # Core formulas and numerical solve
src/safety_stock/cli.py         # Batch runner from JSON
tests/test_calculator.py        # Unit tests for core behavior
examples/scenarios.json         # Ready-to-run examples
```