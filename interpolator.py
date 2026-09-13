from __future__ import annotations
import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

# Menu de méthodes possibles pour YieldCurve
class InterpolationMethod(Enum):
    LINEAR = "Linear"
    LOG_LINEAR = "LogLinear"
    CUBIC_SPLINE_NATURAL = "CubicSplineNatural"        # f''(x0)=f''(xn)=0
    CUBIC_SPLINE_CLAMPED_D0 = "CubicSplineClampedD0"   # f'(x0)=f'(xn)=0
    KRUGER = "Kruger"                                  # spline monotone d'Hermite

# Représentation des points : x = t et y = z(t) ou z(t)*t
@dataclass(frozen=True)
class XYPoint:
    x: float
    y: float

# Recherche dichotomique pour trouver l'intervalle [xs[i], xs[i+1]]
# contenant la valeur x. Retourne l'indice i du segment.
def _find_segment(xs: List[float], x: float) -> int:
    l, h = 0, len(xs) - 2
    while l <= h:
        mid = (l+ h) // 2
        if xs[mid] <= x <= xs[mid + 1]:
            return mid
        if x < xs[mid]:
            h = mid - 1
        else:
            l = mid + 1
    return max(0, min(len(xs) - 2, l))

# Gère l'extrapolation plate :
# si x est en dehors des bornes, retourne la valeur la plus proche. Sinon retourne None.
def _flat_extrapolation(xs: List[float], ys: List[float], x: float) -> Optional[float] :
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    return None

# Remplit les coefficients internes du système tridiagonal
# nécessaire au calcul des secondes dérivées de la spline cubique.
def _fill_spline_interior(
    a: List[float],
    b: List[float],
    c: List[float],
    d: List[float],
    h: List[float],
    ys: List[float],
) -> None:

    n = len(ys)
    for i in range(1, n - 1):
        a[i] = h[i-1]
        b[i] = 2.0 * (h[i-1] + h[i])
        c[i] = h[i]
        d[i] = 6.0 * (
            (ys[i+1] - ys[i]) / h[i]
            - (ys[i] - ys[i-1]) / h[i-1]
        )

# Résout un système linéaire tridiagonal à l'aide
# de l'algorithme de Thomas. Retourne la solution (secondes dérivées de la spline).
def _solve_tridiagonal(a : List[float], b : List[float], c : List[float], d : List[float]) -> List[float]:
    n = len(d)
    cp = [0.0] * n
    dp = [0.0] * n

    cp[0] = c[0] / b[0] if b[0] != 0 else 0.0
    dp[0] = d[0] / b[0] if b[0] != 0 else 0.0

    for i in range(1, n):
        den = b[i] - a[i] * cp[i-1]
        if abs(den) < 1e-18:
            raise ValueError("Spline system is singular")
        cp[i] = c[i] / den if i < n-1 else 0.0
        dp[i] = (d[i] - a[i] * dp[i-1]) / den

    M = [0.0] * n
    M[-1] = dp[-1]
    for i in range(n-2, -1, -1):
        M[i] = dp[i] - cp[i] * M[i+1]

    return M

# Calcule les espacements h[i] = xs[i+1] - xs[i]
# et vérifie que les abscisses sont strictement croissantes.
def _compute_h(xs : List[float]) -> List[float]:
    h = [xs[i+1] - xs[i] for i in range(len(xs)-1)]
    if any(hi <= 0 for hi in h):
        raise ValueError("x doit être strictement croissant")
    return h

# Calcule les pentes nécessaires à l'interpolation de Kruger (spline d'Hermite monotone).
def _compute_kruger_slopes(xs : List[float], ys : List[float]) -> Tuple[List[float], List[float]]:
    n = len(xs)
    h = _compute_h(xs)
    delta = [(ys[i+1] - ys[i]) / h[i] for i in range(n-1)]

    m = [0.0] * n
    m[0], m[-1] = delta[0], delta[-1]

    for i in range(1, n-1):
        if delta[i-1] * delta[i] <= 0:
            m[i] = 0.0
        else:
            w1 = 2*h[i] + h[i-1]
            w2 = h[i] + 2*h[i-1]
            m[i] = (w1+w2)/(w1/delta[i-1] + w2/delta[i])

    return h, m

# Construire une spline cubique (natural ou clamped) en calculant les secondes
# dérivées aux points donnés
class _NaturalOrClampedSpline:
    def __init__(self, xs : List[float], ys : List[float], clamped : bool, d0 : float = 0.0, dn : float = 0.0) -> None:
        if len(xs) < 2:
            raise ValueError("Besoin d'au moins 2 points")

        self.xs, self.ys = xs, ys
        n = len(xs)
        h = _compute_h(xs)

        a = [0.0] * n
        b = [0.0] * n
        c = [0.0] * n
        d = [0.0] * n

        if not clamped:
            b[0] = b[-1] = 1.0
        else:
            b[0], c[0] = 2*h[0], h[0]
            d[0] = 6*((ys[1]-ys[0])/h[0] - d0)
            a[-1], b[-1] = h[-1], 2*h[-1]
            d[-1] = 6*(dn - (ys[-1]-ys[-2])/h[-1])

        _fill_spline_interior(a, b, c, d, h, ys)

        self.M = _solve_tridiagonal(a, b, c, d)
        self.h = h

    # Évaluer la spline en un point
    def value(self, x: float) -> float:
        xs, ys, M, h = self.xs, self.ys, self.M, self.h

        # Gestion de l'Extrapolation plate avec la fonction _flat_extrapolation
        flat = _flat_extrapolation(xs, ys, x)
        if flat is not None:
            return flat

        # Trouver le segment contenant x (pour interpoler segment par segment)
        i = _find_segment(xs, x)
        xi, xi1 = xs[i], xs[i+1]
        hi = h[i]

        # Calcul des coefficients A et B (combien chaque point voisin influence la valeur interpolée)
        # A + B = 1
        A = (xi1 - x) / hi
        B = (x - xi) / hi

        # Formule spline cubique
        return (
            A * ys[i] + B * ys[i+1]
            + ((A**3 - A) * M[i] + (B**3 - B) * M[i+1]) * (hi**2) / 6.0
        )

class _KrugerSpline:
    def __init__(self, xs : List[float], ys : List[float]) -> None:
        if len(xs) < 2:
            raise ValueError("Besoin d'au moins 2 points")

        self.xs, self.ys = xs, ys
        self.h, self.m = _compute_kruger_slopes(xs, ys)

    # Calcul de l'interpolation
    def value(self, x: float) -> float:
        xs, ys, h, m = self.xs, self.ys, self.h, self.m

        # Gestion de l'Extrapolation plate avec la fonction _flat_extrapolation
        flat = _flat_extrapolation(xs, ys, x)
        if flat is not None:
            return flat

        # Trouver le segment contenant x (pour interpoler segment par segment)
        i = _find_segment(xs, x)
        xi, xi1 = xs[i], xs[i+1]
        hi = h[i]

        # Normaliser la position dans le segment
        t = (x - xi) / hi

        # Calcul des bases de Hermite
        h00 = (2*t**3 - 3*t**2 + 1)
        h10 = (t**3 - 2*t**2 + t)
        h01 = (-2*t**3 + 3*t**2)
        h11 = (t**3 - t**2)

        # Formule Hermite finale
        return (
            h00 * ys[i]
            + h10 * hi * m[i]
            + h01 * ys[i+1]
            + h11 * hi * m[i+1]
        )

# Donner une valeur interpolée f(x) pour n'importe quel x
class XYFunction:
    def __init__(self, points: List[XYPoint], method: InterpolationMethod = InterpolationMethod.LINEAR):

        # Vérifier qu'on a au moins 1 point
        if not points:
            raise ValueError("XYFunction a besoin d'au moins 1 point")

        # Trier les points
        self.points = sorted(points, key=lambda p: p.x)

        # Choisir la méthode (linéaire, log-linéaire, spline, Kruger..)
        self.method = method

        # Construire listes xs et ys
        self._xs = [p.x for p in self.points]
        self._ys = [p.y for p in self.points]

        self._spline: Optional[object] = None

        # Contrainte pour spline/Kruger : au moins 2 points
        if len(self._xs) < 2:
            return

        # Construire la méthode avancée si ≥ 2 points
        if self.method == InterpolationMethod.CUBIC_SPLINE_NATURAL:
            self._spline = _NaturalOrClampedSpline(self._xs, self._ys, clamped=False)
        elif self.method == InterpolationMethod.CUBIC_SPLINE_CLAMPED_D0:
            self._spline = _NaturalOrClampedSpline(self._xs, self._ys, clamped=True, d0=0.0, dn=0.0)
        elif self.method == InterpolationMethod.KRUGER:
            self._spline = _KrugerSpline(self._xs, self._ys)

    # Calcul valeur interpolée
    def value(self, x: float) -> float:
        xs, ys = self._xs, self._ys

        # Fonction constante si 1 point (même y)
        if len(xs) == 1:
            return ys[0]

        # Gestion de l'Extrapolation plate avec la fonction _flat_extrapolation
        flat = _flat_extrapolation(xs, ys, x)
        if flat is not None:
            return flat

        # Si on a une spline/Kruger construite
        if self._spline is not None:
            return self._spline.value(x)

        # Sinon : linear / log-linear segment par segment
        # Trouver le bon segment
        i = _find_segment(xs, x)
        x1, y1 = xs[i], ys[i]
        x2, y2 = xs[i+1], ys[i+1]

        # Cas LINEAR
        if self.method == InterpolationMethod.LINEAR:
            return y1 + (y2 - y1) * (x - x1) / (x2 - x1)

        # Cas LOG_LINEAR
        if self.method == InterpolationMethod.LOG_LINEAR:
            if y1 <= 0 or y2 <= 0:
                return y1 + (y2 - y1) * (x - x1) / (x2 - x1)
            return math.exp(math.log(y1) + (math.log(y2) - math.log(y1)) * (x - x1) / (x2 - x1))

        # Sécurité : si une méthode non gérée, renvoyer linéaire
        return y1 + (y2 - y1) * (x - x1) / (x2 - x1)