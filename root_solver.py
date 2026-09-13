from enum import Enum
from typing import Callable, Dict, List, Optional


class SolvingMethod(Enum):
    BISECTION = "Bisection"
    NEWTON = "Newton"
    BRENT = "Brent"


class RootSolver:
    def __init__(
        self,
        f: Callable[[float], float],
        lower: float,
        upper: float,
        tol_x: float = 1e-10,
        tol_y: float = 1e-10,
        max_iter: int = 200,
        method: SolvingMethod = SolvingMethod.BRENT,
    ) -> None:
        self.f = f
        self.lower = lower
        self.upper = upper
        self.tol_x = tol_x
        self.tol_y = tol_y
        self.max_iter = max_iter
        self.method = method
        self.history: List[Dict[str, float]] = []

    # Outils
    def _check_bracket(self, a: float, b: float) -> tuple[float, float]:
        fa = self.f(a)
        fb = self.f(b)

        if fa * fb > 0:
            raise ValueError("Root not bracketed")

        return fa, fb

    def _converged(self, fx: float, a: float, b: float) -> bool:
        return abs(fx) < self.tol_y or abs(b - a) < self.tol_x

    def _log(self, k: int, x: float, fx: float, x1: float, x2: float) -> None:
        self.history.append(
            {
                "Try": k,
                "x": x,
                "fx": fx,
                "x1": x1,
                "x2": x2,
                "diff": abs(x2 - x1),
            }
        )

    # Méthodes privées pour Brent
    @staticmethod
    def _det3(
        a11: float, a12: float, a13: float,
        a21: float, a22: float, a23: float,
        a31: float, a32: float, a33: float,
    ) -> float:
        return (
            a11 * (a22 * a33 - a23 * a32)
            - a12 * (a21 * a33 - a23 * a31)
            + a13 * (a21 * a32 - a22 * a31)
        )

    def _quad_root_in_bracket(
        self,
        x0: float, y0: float,
        x1: float, y1: float,
        x2: float, y2: float,
        lo: float, hi: float,
    ) -> Optional[float]:
        """
        - Construit une parabole y = A x^2 + B x + C
          passant par (x0,y0), (x1,y1), (x2,y2)
        - Calcule ses racines
        - Retourne celle qui est dans [lo, hi], sinon None
        """

        # Déterminant principal
        d = self._det3(
            x0 * x0, x0, 1.0,
            x1 * x1, x1, 1.0,
            x2 * x2, x2, 1.0
        )

        # Si le déterminant est quasi nul → points presque alignés
        if abs(d) < 1e-18:
            return None

        # Déterminants pour A, B, C (règle de Cramer)
        dA = self._det3(
            y0, x0, 1.0,
            y1, x1, 1.0,
            y2, x2, 1.0
        )

        dB = self._det3(
            x0 * x0, y0, 1.0,
            x1 * x1, y1, 1.0,
            x2 * x2, y2, 1.0
        )

        dC = self._det3(
            x0 * x0, x0, y0,
            x1 * x1, x1, y1,
            x2 * x2, x2, y2
        )

        A = dA / d
        B = dB / d
        C = dC / d

        # Si la parabole est presque une droite → résolution linéaire
        if abs(A) < 1e-16:
            if abs(B) < 1e-16:
                return None
            r = -C / B
            return r if lo <= r <= hi else None

        # Calcul du discriminant
        disc = B * B - 4.0 * A * C
        if disc < 0.0:
            return None

        sqrt_disc = disc ** 0.5

        # Racines de la parabole
        r1 = (-B - sqrt_disc) / (2.0 * A)
        r2 = (-B + sqrt_disc) / (2.0 * A)

        # On conserve uniquement celles dans le bracket
        candidates: List[float] = []
        if lo <= r1 <= hi:
            candidates.append(r1)
        if lo <= r2 <= hi:
            candidates.append(r2)

        if not candidates:
            return None

        # Si plusieurs racines : prendre la racine la plus proche du dernier point x2
        # tri par la clé dans l'ordre croissant
        candidates.sort(key=lambda r: abs(r - x2))
        return candidates[0]

    # Pas Brent
    def _brent_step(
        self,
        x0: float, y0: float,
        x1: float, y1: float,
        x2: float, y2: float,
        a: float, b: float,
    ) -> float:
        lo, hi = (a, b) if a < b else (b, a)

        # Tentative -> racines de la parabole
        x_new = self._quad_root_in_bracket(x0, y0, x1, y1, x2, y2, lo, hi)

        # Si tentative échoue -> bisection
        return x_new if x_new is not None else 0.5 * (a + b)

    # Pas Sécante
    def _secant_step(
            self,
            x0: float,
            f0: float,
            x1: float,
            f1: float,
    ) -> float:
        denom = f1 - f0
        if abs(denom) < 1e-14:
            return 0.5 * (x0 + x1)
        return x1 - f1 * (x1 - x0) / denom

    # Fonction Principale
    def solve(self) -> float:
        self.history = []
        if self.method == SolvingMethod.BISECTION:
            return self._bisection()
        if self.method == SolvingMethod.NEWTON:
            return self._newton()
        return self._brent()

    # Méthode BISECTION
    def _bisection(self) -> float:
        a = self.lower
        b = self.upper
        fa = self.f(a)
        fb = self.f(b)

        if fa * fb > 0:
            raise ValueError("Root not bracketed")

        self._log(1, a, fa, a, b)
        self._log(2, b, fb, a, b)

        for k in range(3, self.max_iter + 1):
            m = 0.5 * (a + b)
            fm = self.f(m)
            if fa * fm < 0:
                b, fb = m, fm
            else:
                a, fa = m, fm
            self._log(k, m, fm, a, b)
            if self._converged(fm, a, b):
                return m
        return 0.5 * (a + b)

    # Méthode NEWTON
    def _newton(self) -> float:
        x1 = self.lower
        x2 = self.upper
        f1 = self.f(x1)
        f2 = self.f(x2)
        self._log(1, x1, f1, x1, x2)
        self._log(2, x2, f2, x1, x2)

        for k in range(3, self.max_iter + 1):
            x = self._secant_step(x1, f1, x2, f2)
            if not (self.lower <= x <= self.upper):
                x = 0.5 * (x1 + x2)
            fx = self.f(x)
            if fx * f1 < 0:
                x2, f2 = x, fx
            else:
                x1, f1 = x, fx
            self._log(k, x, fx, x1, x2)

            if self._converged(fx, x1, x2):
                return x
        return x

    # Méthode BRENT
    def _brent(self) -> float:
        ## Initialisation du bracket
        a, b = self.lower, self.upper
        fa, fb = self.f(a), self.f(b)

        # Vérification de la condition de bracket
        if fa * fb > 0:
            raise ValueError("Root not bracketed")

        ## Initialisation des 3 premiers points
        x0, y0 = a, fa  # 1er point (borne gauche)
        x1, y1 = b, fb  # 2e point (borne droite)
        x2 = self._secant_step(x0, y0, x1, y1)  # # 3e point via la sécante

        # On force le point à rester dans le bracket
        if not (min(a, b) <= x2 <= max(a, b)):
            x2 = 0.5 * (a + b)

        y2 = self.f(x2)

        # Mise à jour du bracket avec ce 3e point
        if fa * y2 < 0:
            b, fb = x2, y2
        else:
            a, fa = x2, y2

        # Log initial
        self._log(1, x0, y0, a, b)
        self._log(2, x1, y1, a, b)
        self._log(3, x2, y2, a, b)

        # Boucle principale de Brent
        for k in range(4, self.max_iter + 1):

            # Critères d’arrêt
            if abs(fb) < self.tol_y or abs(b - a) < self.tol_x:
                return b if abs(fb) < abs(fa) else a

            x_new = self._brent_step(x0, y0, x1, y1, x2, y2, a, b)
            f_new = self.f(x_new)

            # Décalage des trois derniers points
            x0, y0 = x1, y1
            x1, y1 = x2, y2
            x2, y2 = x_new, f_new

            # Mise à jour du bracket
            if fa * f_new < 0:
                b, fb = x_new, f_new
            else:
                a, fa = x_new, f_new

            self._log(k, x_new, f_new, a, b)

        # Retour de secours si non convergence de la racine
        return b if abs(fb) < abs(fa) else a