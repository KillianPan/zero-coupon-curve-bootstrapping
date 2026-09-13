import xlwings as xw
import datetime as dt
import time

from YieldCurve import ZCInterpolation
from curve_solver import CurveBootstrapper
from interpolator import InterpolationMethod
from root_solver import SolvingMethod
from Utils import *

# ---- Timer global ----
RUN_COUNT = 0
MIN_TIME = float("inf")
MAX_TIME = 0.0

# Lecture des valeurs Excel
def read_excel_inputs(sheet):
    # Récupération de la pricing date
    pricing_date = sheet.range("pricing_date").value
    if isinstance(pricing_date, dt.datetime):
        # On convertit en date simple
        pricing_date = pricing_date.date()

    # Notionnel du swap
    notional = float(sheet.range("notional").value)

    tenors_raw = sheet.range("tenors").expand("down").options(ndim=1).value
    swap_rates_raw = sheet.range("swap_rate").expand("down").options(ndim=1).value

    tenors = []
    swap_rates = []

    for t, r in zip(tenors_raw, swap_rates_raw):
        if t in (None, "") or r in (None, ""):
            continue

        tenors.append(str(t).strip())

        rr = float(r)

        # Si le taux est en %, on le repasse en décimal
        if rr > 1:
            rr /= 100

        swap_rates.append(rr)

    return pricing_date, notional, tenors, swap_rates


# Conversion strings vers enums
def parse_enums(sheet):
    # NEWTON, BRENT, LINEAR, LOG_LINEAR, etc.

    method_str = str(sheet.range("method_value").value).strip().upper()
    interp_str = str(sheet.range("interpolation_value").value).strip().upper()

    solver_method = SolvingMethod[method_str]
    interp_method = InterpolationMethod[interp_str]

    # Ici on fixe le type d'interpolation ZC (à modifier)
    zc_interp = ZCInterpolation.LINEAR_ZT

    return solver_method, interp_method, zc_interp

@xw.sub()
def run() -> None:
    global RUN_COUNT, MIN_TIME, MAX_TIME

    # Début du chronomètre
    total_start = time.perf_counter()

    wb = xw.Book.caller()
    sheet = wb.sheets.active

    # Lecture des inputs depuis Excel
    pricing_date, notional, tenors, swap_rates = read_excel_inputs(sheet)
    solver_method, interp_method, zc_interp = parse_enums(sheet)

    # Calcul du spot date (T+2)
    start_date = add_business_days(pricing_date, 2)
    sheet.range("start_date").value = start_date

    # ----- Bootstrap de la courbe -----
    bootstrapper = CurveBootstrapper(
        pricing_date=pricing_date,
        notional=notional,
        tenors=tenors,
        swap_rates=swap_rates,
        solver_method=solver_method,
        interp_method=interp_method,  # dépend du choix Excel
        zc_interp=zc_interp,          # fixé ici
        lower=-0.05,
        upper=0.15,
    )

    result = bootstrapper.bootstrap()

    # ----- Gestion du timer -----
    total_time = time.perf_counter() - total_start

    RUN_COUNT += 1
    MIN_TIME = min(MIN_TIME, total_time)
    MAX_TIME = max(MAX_TIME, total_time)

    # Affichage multi-ligne plus lisible dans Excel
    timer_text = (
        f"{total_time:.4f}  Time (s)\n"
        f"{RUN_COUNT}  Total\n"
        f"{MIN_TIME:.4f} / {MAX_TIME:.4f}  Min / Max"
    )
    sheet.range("timer").value = timer_text

    # ----- Reconstruction de la courbe pour affichage -----
    curve = result.as_curve(
        pricing_date=pricing_date,
        interp_method=interp_method,
        zc_interp=zc_interp,
    )

    # ----- Tableau ZC (End date / t / zc / DF) -----
    zc_rows = []
    for ed, t, z in zip(result.end_dates, result.times, result.zc_rates):
        df = curve.discount_factor(ed)
        zc_rows.append([ed, t, z, df])

    # On nettoie la zone avant d'écrire (évite résidus anciens calculs)
    sheet.range("zc_tables").expand().clear_contents()
    sheet.range("zc_tables").value = zc_rows

    # ----- Historique du solveur -----
    sheet.range("solver_log").expand().clear_contents()
    if result.solver_table:
        sheet.range("solver_log").value = result.solver_table

    # ----- Construction des forwards -----
    sheet.range("fwd_start").expand().clear_contents()

    fwd_tenor = sheet.range("fwd_tenor").value
    basis_str = str(sheet.range("basis").value).strip().upper()

    # Choix de la base day count
    basis_val = 360.0 if basis_str == "ACT/360" else 365.0

    fwd_rows = build_forward_table(
        curve,
        pricing_date,
        result.end_dates[-1],
        step_tenor=fwd_tenor,
        basis=basis_val,
    )

    sheet.range("fwd_start").value = fwd_rows

if __name__ == "__main__":
    xw.Book("Interface.xlsm").set_mock_caller()
    run()