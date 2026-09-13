import math
from enum import Enum
from datetime import date
from typing import List

from Utils import year_fraction_act360, year_fraction_act365
from interpolator import XYFunction, XYPoint, InterpolationMethod

# Type d’interpolation du zéro coupon
class ZCInterpolation(Enum):
    LINEAR_Z = "LinearZ"
    LINEAR_ZT = "LinearZxT"

# Courbe de taux
class YieldCurve:
    def __init__(
        self,
        pricing_date: date,
        times: List[float],
        zc_rates: List[float],
        interp_method: InterpolationMethod = InterpolationMethod.LINEAR,
        zc_interp: ZCInterpolation = ZCInterpolation.LINEAR_ZT,
    ) -> None:

        self.pricing_date: date = pricing_date
        self.times: List[float] = list(times)
        self.zc_rates: List[float] = list(zc_rates)
        self.interp_method: InterpolationMethod = interp_method
        self.zc_interp: ZCInterpolation = zc_interp
        self._f: XYFunction
        self._rebuild()

    # Construction fonction interpolée
    def _rebuild(self) -> None:

        if len(self.times) != len(self.zc_rates) or len(self.times) == 0:
            raise ValueError(
                "YieldCurve requires non-empty times and zc_rates of same length"
            )

        # Choix du mapping zéro coupon
        if self.zc_interp == ZCInterpolation.LINEAR_Z:
            pts: List[XYPoint] = [
                XYPoint(t, r) for t, r in zip(self.times, self.zc_rates)
            ]
        else:
            pts = [
                XYPoint(t, r * t)
                for t, r in zip(self.times, self.zc_rates)
            ]

        self._f = XYFunction(pts, method=self.interp_method)

    # Calcul zéro coupon
    def zero_rate(self, t: float) -> float:

        # Flat extrapolation
        if t <= self.times[0]:
            return self.zc_rates[0]

        if t >= self.times[-1]:
            return self.zc_rates[-1]

        y: float = self._f.value(t)

        if self.zc_interp == ZCInterpolation.LINEAR_Z:
            return y

        return y / t

    # Discount factor
    def discount_factor(self, d: date) -> float:

        t: float = year_fraction_act365(self.pricing_date, d)
        r: float = self.zero_rate(t)

        return math.exp(-r * t)

    # Outils
    def day_count_fraction_360(self, start: date, end: date) -> float:
        return year_fraction_act360(start, end)

