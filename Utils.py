from datetime import timedelta, date
from dateutil.relativedelta import relativedelta
from typing import List, Any

# Year fractions
def year_fraction_act365(start: date, end: date) -> float:
    return (end - start).days / 365.0

def year_fraction_act360(start: date, end: date) -> float:
    return (end - start).days / 360.0

# Outils tenor et dates
def add_tenor(start_date: date, tenor: str) -> date:

    tenor = str(tenor).strip().upper()
    if tenor.endswith("M"):
        return start_date + relativedelta(months=int(tenor[:-1]))
    if tenor.endswith("Y"):
        return start_date + relativedelta(years=int(tenor[:-1]))
    raise ValueError("Unsupported tenor")

# Outils Business day
def add_business_days(d: date, n: int) -> date:

    d_out: date = d
    added: int = 0
    while added < n:
        d_out += timedelta(days=1)
        if d_out.weekday() < 5:
            added += 1
    return d_out

def adjust_following(d: date) -> date:

    d_out: date = d
    while d_out.weekday() >= 5:
        d_out += timedelta(days=1)
    return d_out

# Outils Forwards
def parse_forward_tenor(s: str) -> int:

    s = str(s).strip().upper()
    if s.endswith("W"):
        return 7 * int(s[:-1])
    if s.endswith("M"):
        raise ValueError("Tenor M not supported")
    raise ValueError(f"Tenor forward non supporté: {s}")

def add_calendar_days(d: date, n_days: int) -> date:
    return d + timedelta(days=n_days)

# Taux Forwards
def forward_rate_1d(
    curve: Any,
    d0: date,
    d1: date,
    basis: float = 360.0,
) -> float:

    ni: int = (d1 - d0).days

    df0: float = curve.discount_factor(d0)
    df1: float = curve.discount_factor(d1)

    return (df0 / df1 - 1.0) * basis / ni

# Constructeur tableau des Forwards
def build_forward_table(
    curve: Any,
    pricing_date: date,
    end_date: date,
    step_tenor: str,
    basis: float = 360.0,
) -> List[list]:

    step_days: int = parse_forward_tenor(step_tenor)
    rows: List[list] = []

    d0: date = pricing_date

    while d0 < end_date:
        d0_adj: date = adjust_following(d0)
        d1: date = add_business_days(d0_adj, 1)

        rate: float = forward_rate_1d(
            curve=curve,
            d0=d0_adj,
            d1=d1,
            basis=basis,
        )

        rows.append([d0_adj, d1, rate])
        d0 = add_calendar_days(d0, step_days)

    return rows