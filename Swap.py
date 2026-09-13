from enum import Enum
from datetime import date
from typing import Tuple, List, Optional, Any

from dateutil.relativedelta import relativedelta
from Cashflow import InterestRateCashflow, RateType



# Paramétrage de la direction du cashflow du swap
class Direction(Enum):
    # Direction du swap leg :
    # - Pay = on paie les flux
    # - Rec = on reçoit les flux
    Pay = -1
    Rec = 1

# Classe principale Swap
class Swap:
    def __init__(
        self,
        notional: float,
        rate: float,
        start_date: date,
        end_date: date,
        ccy: str,
    ) -> None:

        # Paramètres du Swap
        self.notional: float = notional
        self.rate: float = rate
        self.start_date: date = start_date
        self.end_date: date = end_date
        self.ccy: str = ccy

        # Legs du swap
        self.pay_leg : Optional[Any] = None
        self.rec_leg : Optional[Any] = None

    # Fonction calculant la valeur actuelle du swap
    def pv(self, curve : Any) -> float:
        return self.pay_leg.pv(curve) + self.rec_leg.pv(curve)

# Génération des périodes annuelles
def annual_periods(start: date, end: date) -> list[tuple[date, date]]:
    periods: list[tuple[date, date]] = []
    d: date = start

    # Boucle temporelle jusqu'à maturité
    while d < end:
        dn: date = d + relativedelta(years=1)

        # Ne pas dépasser la maturité finale
        if dn > end:
            dn = end

        periods.append((d, dn))
        d = dn

    return periods

# Classe Leg
class Leg:
    def __init__(self, swap: Swap, direction: Direction) -> None:
        self.swap: Swap = swap
        self.direction: Direction = direction

        # Liste des cashflows associés à la jambe
        self.schedule: list[InterestRateCashflow] = []

    # Fonction calculant la PV de la jambe
    def pv(self, curve : Any) -> float:
        sign: int = self.direction.value
        total: float = sum(cf.pv(curve) for cf in self.schedule)
        return sign * total

# Jambe fixe du swap
class FixedLeg(Leg):
    def __init__(self, swap: Swap, direction: Direction) -> None:
        super().__init__(swap, direction)
        self.build()

    # Construction du calendrier de cashflows
    def build(self) -> None:

        periods = annual_periods(
            self.swap.start_date,
            self.swap.end_date,
        )

        self.schedule = [
            InterestRateCashflow(
                notional=self.swap.notional,
                start_date=s,
                end_date=e,
                rate_type=RateType.FIXED,
                fixed_rate=self.swap.rate,
            )
            for (s, e) in periods
        ]

# Jambe flottante du swap
class FloatingLeg(Leg):
    def __init__(self, swap: Swap, direction: Direction) -> None:
        super().__init__(swap, direction)
        self.build()

    # Construction du calendrier flottant
    def build(self) -> None:
        periods = annual_periods(
            self.swap.start_date,
            self.swap.end_date,
        )

        self.schedule = [
            InterestRateCashflow(
                notional=self.swap.notional,
                start_date=s,
                end_date=e,
                rate_type=RateType.FLOAT_COMPOUNDED,
            )
            for (s, e) in periods
        ]