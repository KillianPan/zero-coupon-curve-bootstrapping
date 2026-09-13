from enum import Enum
from datetime import date
from typing import Any

# Type de cashflow
class RateType(Enum):
    FIXED = "Fixed"
    FLOAT_COMPOUNDED = "FloatCompounded"

# Cashflow générique
class Cashflow:
    def __init__(self, amount: float, payment_date: date) -> None:
        self.amount: float = amount
        self.payment_date: date = payment_date

    def pv(self, curve: Any) -> float:
        return self.amount * curve.discount_factor(self.payment_date)

# Cashflow taux d'intérêt
class InterestRateCashflow:
    def __init__(
        self,
        notional: float,
        start_date: date,
        end_date: date,
        rate_type: RateType,
        fixed_rate: float | None = None,
    ) -> None:

        self.notional: float = notional
        self.start_date: date = start_date
        self.end_date: date = end_date
        self.payment_date: date = end_date
        self.rate_type: RateType = rate_type
        self.fixed_rate: float | None = fixed_rate

    # Calcul montant du cashflow
    def amount(self, curve: Any) -> float:

        # FIXED RATE LEG
        if self.rate_type == RateType.FIXED:

            yf: float = curve.day_count_fraction_360(
                self.start_date,
                self.end_date,
            )

            return self.notional * float(self.fixed_rate or 0.0) * yf

        # FLOAT COMPOUNDED LEG
        df_start: float = curve.discount_factor(self.start_date)
        df_end: float = curve.discount_factor(self.end_date)

        return self.notional * (df_start / df_end - 1.0)

    # PV du cashflow
    def pv(self, curve: Any) -> float:
        amt: float = self.amount(curve)
        return amt * curve.discount_factor(self.payment_date)