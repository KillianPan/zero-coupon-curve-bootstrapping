# Zero-Coupon Curve Bootstrapping
Python project bootstrapping a EUR zero-coupon yield curve from OIS/€STR swap rates, with fixed/floating leg pricing, root-solvers (bisection, Newton, Brent) and interpolation methods (linear, log-linear, cubic &amp; Kruger splines).

The project is used through an Excel interface (`Interface.xlsm`), powered by
[xlwings](https://www.xlwings.org/), which calls the Python code in the
background.

## Table of contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Code organization](#code-organization)
- [Technical choices](#technical-choices)
- [Challenges encountered](#challenges-encountered)
- [Authors](#authors)

## Requirements

- Python 3.10 or higher
- Microsoft Excel (required, the project drives an `.xlsm` workbook via xlwings)

## Installation

```bash
# Clone the repository
git clone https://github.com/KillianPan/zero-coupon-curve-bootstrapping.git
cd zero-coupon-curve-bootstrapping

# Install Python dependencies
pip install -r requirements.txt
```

## Usage

### Option 1 — From Excel (recommended)

1. Open `Interface.xlsm` in Excel.
2. Enable macros if prompted.
3. Fill in the market parameters in the named ranges provided:
   - `pricing_date`: valuation date
   - `notional`: swap notional
   - `tenors` / `swap_rate`: list of quoted tenors and swap rates
   - `method_value`: solving method (`BISECTION`, `NEWTON` or `BRENT`)
   - `interpolation_value`: interpolation method (`LINEAR`, `LOG_LINEAR`,
     `CUBIC_SPLINE_NATURAL`, `CUBIC_SPLINE_CLAMPED_D0` or `KRUGER`)
   - `fwd_tenor` / `basis`: parameters for the forward rate table
4. Run the macro linked to the `run()` function (button in the workbook).
5. Results are automatically written to the `start_date`, `zc_tables`,
   `solver_log` and `fwd_start` ranges.

### Option 2 — From a terminal

`Interface.xlsm` must be in the same folder as `main.py`.

```bash
python3 main.py
```

The script automatically connects to the workbook (`set_mock_caller`) and
runs the bootstrap using the values already present in the Excel file.

## Code organization

| File | Role |
|---|---|
| `main.py` | Entry point. Reads parameters from Excel, runs the bootstrap, writes back the results. |
| `curve_solver.py` | Central module: orchestrates the bootstrap of the ZC curve from market swaps. |
| `Swap.py` | Swap logic: fixed/floating legs, calculation conventions, cashflow direction. |
| `Cashflow.py` | Cashflow definitions (fixed and compounded floating) and present value calculation. |
| `YieldCurve.py` | Bridges finance and maths: date-to-time conversion, zero rate and discount factor calculation. |
| `interpolator.py` | Generic interpolation engine (hand-coded binary search for the interval, linear, log-linear, cubic splines, Kruger). |
| `root_solver.py` | Generic numerical solvers (Bisection, Newton, Brent) to find the root of a function f(x) = 0. |
| `Utils.py` | Utility functions: year fractions, business day handling, forward rate calculation. |
| `Interface.xlsm` | Excel interface for entering parameters and viewing results. |

### Dependency diagram

The project is organized into independent layers:

- **Products** (`Swap.py`, `Cashflow.py`) — product logic
- **Yield curve** (`YieldCurve.py`) — yield curve
- **Math** (`interpolator.py`, `root_solver.py`, `Utils.py`) — generic tools with no business dependency
- **curve_solver.py** — ties all the pieces together to perform the bootstrap

## Technical choices

### Binary search in `interpolator.py`

Rather than importing the standard library's `bisect` module, a binary
search was hand-coded (`_find_segment`) to find the interval `[xi, xi+1]`
containing a point to interpolate, in O(log n). This matters because the
solver calls this function thousands of times during the bootstrap.

### `curve_solver.py`, the central module

For each tenor, `CurveBootstrapper.bootstrap()`:
1. computes the maturity date from the spot date (T+2);
2. converts that date into continuous time (ACT/365);
3. defines a `PV(z)` function that builds a temporary curve with the
   candidate rate, creates the corresponding swap and computes its present value;
4. uses a `RootSolver` (Bisection, Newton or Brent) to find the zero-coupon
   rate `z` that sets this PV to zero.

## Challenges encountered

### Dates and weekends

Fixed a reference error: floating leg interest must be computed from the
swap's `start_date` (the "Spot Date", T+2), not the `pricing_date`. Swap end
dates falling on a weekend are also shifted to the next business day,
otherwise the year fractions — and therefore the ZC rates — were incorrect.

### Zero-coupon extrapolation

The `zero_rate()` method initially extrapolated `z × t` and then divided by
`t`, which caused a numerical blow-up for maturities very close to the spot
date (division by a time close to zero). The fix returns the constant zero
rate directly outside the calibrated interval (flat extrapolation), avoiding
this unstable division.

### Log-linear interpolation

The `LINEAR_ZT` mode (interpolation on `r × t`) is incompatible with the
`LOG_LINEAR` method, which requires taking the logarithm of the interpolated
values. The `LINEAR_Z` mode (direct interpolation on rates `r`) must be used
so that the log-linear formula (`exp(ln(y1) + …)`) stays mathematically valid.

## Authors

Project developed as part of a Master's-level (M1) market finance course.
