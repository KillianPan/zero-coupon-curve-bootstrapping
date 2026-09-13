from __future__ import annotations
from dataclasses import dataclass
from typing import List
from datetime import date, timedelta

from Utils import add_business_days, add_tenor, year_fraction_act365
from interpolator import InterpolationMethod
from YieldCurve import YieldCurve, ZCInterpolation
from Swap import Swap, FixedLeg, FloatingLeg, Direction
from root_solver import RootSolver, SolvingMethod


# Contient le résultat complet du bootstrap :
# - les temps en années
# - les taux zéro-coupon calibrés
# - les dates de maturité
# - l'historique du solveur (pour export Excel)
@dataclass
class BootstrapResult:
    times: List[float]
    zc_rates: List[float]
    end_dates: List[date]
    solver_table: List[List[float]]

    # Construit une YieldCurve à partir des résultats du bootstrap
    def as_curve(
        self,
        pricing_date: date,
        interp_method: InterpolationMethod = InterpolationMethod.LINEAR,
        zc_interp: ZCInterpolation = ZCInterpolation.LINEAR_ZT,
    ) -> YieldCurve:
        return YieldCurve(
            pricing_date,
            self.times,
            self.zc_rates,
            interp_method=interp_method,
            zc_interp=zc_interp,
        )


# Classe responsable du bootstrap de la courbe zéro-coupon
# à partir de swaps de maturités et taux donnés.
class CurveBootstrapper:

    # Initialise les paramètres nécessaires au bootstrap :
    # - date de pricing
    # - notionnel
    # - maturités (tenors)
    # - taux swap du marché
    # - paramètres du solveur
    # - méthode d'interpolation
    def __init__(
        self,
        pricing_date: date,
        notional: float,
        tenors: List[str],
        swap_rates: List[float],
        solver_method: SolvingMethod = SolvingMethod.BRENT,
        lower: float = -0.05,
        upper: float = 0.15,
        interp_method: InterpolationMethod = InterpolationMethod.LOG_LINEAR,
        zc_interp: ZCInterpolation = ZCInterpolation.LINEAR_ZT,
        ccy: str = "EUR",
    ) -> None:

        if len(tenors) != len(swap_rates):
            raise ValueError("tenors and swap_rates must have the same length")

        self.pricing_date = pricing_date
        self.notional = notional
        self.tenors = tenors
        self.swap_rates = swap_rates

        self.solver_method = solver_method
        self.lower = lower
        self.upper = upper

        self.interp_method = interp_method
        self.zc_interp = zc_interp

        self.ccy = ccy

    # Méthode principale qui réalise le bootstrap :
    # Pour chaque maturité, on résout un taux zéro-coupon
    # tel que le swap correspondant ait une PV nulle.
    def bootstrap(self) -> BootstrapResult:

        times: List[float] = []
        zc_rates: List[float] = []
        end_dates: List[date] = []
        solver_table: List[List[float]] = []

        # Spot date = T+2 (standard marché)
        spot_date: date = add_business_days(self.pricing_date, 2)

        # On boucle sur chaque maturité
        for i, tenor in enumerate(self.tenors):

            # Calcul de la date de fin du swap
            end_date: date = add_tenor(spot_date, tenor)

            # Ajustement week-end
            while end_date.weekday() >= 5:
                end_date = end_date + timedelta(days=1)

            end_dates.append(end_date)

            # Conversion en temps continu (année ACT/365)
            t: float = year_fraction_act365(self.pricing_date, end_date)

            # Fonction dont on cherche la racine :
            # On veut PV(swap) = 0
            def pv_for_rate(zc: float) -> float:

                # On construit une courbe temporaire
                curve = YieldCurve(
                    self.pricing_date,
                    times + [t],
                    zc_rates + [zc],
                    interp_method=self.interp_method,
                    zc_interp=self.zc_interp,
                )

                # On construit le swap correspondant
                swap = Swap(
                    self.notional,
                    self.swap_rates[i],
                    spot_date,
                    end_date,
                    self.ccy,
                )

                swap.pay_leg = FixedLeg(swap, Direction.Pay)
                swap.rec_leg = FloatingLeg(swap, Direction.Rec)

                # On retourne la PV du swap
                return swap.pv(curve)

            # Solveur numérique pour trouver zc tel que PV = 0
            solver = RootSolver(
                pv_for_rate,
                lower=self.lower,
                upper=self.upper,
                method=self.solver_method,
            )

            zc: float = solver.solve()

            # On stocke l'historique du solveur (pour Excel)
            for h in solver.history:
                solver_table.append([
                    tenor,
                    h["Try"],
                    h["x"],
                    h["fx"],
                    h["x1"],
                    h["x2"],
                    h["diff"],
                ])

            # On ajoute le point calibré à la courbe
            times.append(t)
            zc_rates.append(zc)

        # On retourne tous les résultats
        return BootstrapResult(
            times=times,
            zc_rates=zc_rates,
            end_dates=end_dates,
            solver_table=solver_table,
        )