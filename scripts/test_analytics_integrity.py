"""
Analytical Integrity Test Suite
================================
Validates cross-module consistency, period accuracy, currency
propagation, and graceful failure handling.

Run:
    python scripts/test_analytics_integrity.py
"""
import sys
import os
import io
import math
import traceback

# Force UTF-8 output so non-ASCII chars survive Windows cp1252 console
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import pandas as pd
import numpy as np

# Make app importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.revenue_engine import (
    compute_monthly_revenue,
    get_monthly_series_from_result,
    compute_integrity_score,
    detect_revenue_column,
    detect_date_column,
    _try_compute_revenue,
)
from app.services.root_cause_analysis import analyze_root_causes
from app.services.forecasting_service import generate_forecast
from app.utils.file_processing import detect_currency, format_currency

# ---------------------------------------------------------------------------
# Console helpers (ASCII-safe)
# ---------------------------------------------------------------------------
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = 0
failed = 0
skipped = 0


def _pass(msg: str):
    global passed
    passed += 1
    print(f"  {GREEN}[PASS]{RESET}  {msg}")


def _fail(msg: str, reason: str = ""):
    global failed
    failed += 1
    detail = f" -- {reason}" if reason else ""
    print(f"  {RED}[FAIL]{RESET}  {msg}{detail}")


def _skip(msg: str):
    global skipped
    skipped += 1
    print(f"  {YELLOW}[SKIP]{RESET}  {msg}")


def _section(title: str):
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")


# ---------------------------------------------------------------------------
# Shared fixture: 24 months of synthetic daily data (20 rows/month)
# ---------------------------------------------------------------------------

def _make_df(n_months=24, currency="USD", country=None, rev_col="Sales",
             introduce_nulls=False, non_numeric=False):
    rng = np.random.default_rng(42)
    dates = pd.date_range("2022-01-01", periods=n_months, freq="MS")
    dates_daily = []
    for d in dates:
        dates_daily.extend([d + pd.Timedelta(days=i) for i in range(20)])

    values = rng.uniform(50_000, 200_000, len(dates_daily))
    if non_numeric:
        values_col = ["N/A" if i % 10 == 0 else str(v) for i, v in enumerate(values)]
    else:
        values_col = list(values)

    df_data = {
        "OrderDate": dates_daily,
        rev_col: values_col,
        "Category": rng.choice(["Electronics", "Apparel", "Home"], len(dates_daily)),
        "Region": rng.choice(["North", "South", "East"], len(dates_daily)),
    }
    if currency:
        df_data["Currency"] = currency
    if country:
        df_data["Country"] = country

    df = pd.DataFrame(df_data)

    if introduce_nulls:
        null_idx = rng.integers(0, len(df), 30)
        df.loc[null_idx, rev_col] = None

    return df


# ---------------------------------------------------------------------------
# TEST 1 -- Dashboard vs Root Cause revenue match
# ---------------------------------------------------------------------------

def test_1_dashboard_vs_root_cause_match():
    _section("TEST 1 -- Dashboard vs Root Cause Revenue Match")

    df = _make_df()
    dashboard = compute_monthly_revenue(df, "OrderDate", "Sales")
    rca = analyze_root_causes(df, "Sales")

    dash_curr = dashboard["current_value"]
    rca_curr = rca.get("current_value", None)

    if rca_curr is None:
        _skip("RCA returned no current_value (change below 3% threshold)")
        return

    rel_diff = abs(dash_curr - rca_curr) / max(abs(dash_curr), 1)
    tol = 0.0001  # 0.01%

    if rel_diff < tol:
        _pass(f"Dashboard current_value == RCA current_value ({dash_curr:,.2f}) within 0.01%")
    else:
        _fail(
            "Dashboard vs RCA current_value mismatch",
            f"Dashboard={dash_curr:,.2f}  RCA={rca_curr:,.2f}  diff={rel_diff*100:.4f}%",
        )

    if dashboard["current_period"] == rca.get("current_period"):
        _pass(f"Period labels match: {dashboard['current_period']}")
    else:
        _fail("Period label mismatch",
              f"Dashboard={dashboard['current_period']}  RCA={rca.get('current_period')}")


# ---------------------------------------------------------------------------
# TEST 2 -- Period Comparison Consistency
# ---------------------------------------------------------------------------

def test_2_period_comparison_consistency():
    _section("TEST 2 -- Period Comparison Consistency")

    df = _make_df()
    result = compute_monthly_revenue(df, "OrderDate", "Sales")

    cv = result["current_value"]
    pv = result["previous_value"]
    cp = result["change_percent"]

    if pv and pv != 0:
        expected_cp = round(((cv - pv) / abs(pv)) * 100, 4)
        diff = abs(expected_cp - cp)
        if diff < 0.001:
            _pass(f"change_percent={cp:.4f}% matches manual calc={expected_cp:.4f}% (diff={diff:.6f})")
        else:
            _fail("change_percent mismatch", f"stored={cp}  manual={expected_cp}  diff={diff}")
    else:
        _skip("previous_value is 0 or None -- cannot verify")

    if result["current_period"] and result["previous_period"]:
        curr_dt = pd.to_datetime(result["current_period"])
        prev_dt = pd.to_datetime(result["previous_period"])
        if curr_dt > prev_dt:
            _pass(f"current_period ({result['current_period']}) > previous_period ({result['previous_period']})")
        else:
            _fail("current_period is not after previous_period")
    else:
        _fail("Period strings missing in result")


# ---------------------------------------------------------------------------
# TEST 3 -- Forecast Input Integrity
# ---------------------------------------------------------------------------

def test_3_forecast_input_integrity():
    _section("TEST 3 -- Forecast Input Integrity")

    df = _make_df(n_months=24)
    rev_result = compute_monthly_revenue(df, "OrderDate", "Sales")
    ts = get_monthly_series_from_result(rev_result)

    if len(ts) == rev_result["n_months"]:
        _pass(f"Monthly series length ({len(ts)}) == revenue_engine n_months ({rev_result['n_months']})")
    else:
        _fail("Length mismatch", f"series={len(ts)}  engine={rev_result['n_months']}")

    if isinstance(ts.index, pd.DatetimeIndex):
        _pass("Monthly series has DatetimeIndex")
    else:
        _fail("Monthly series does NOT have DatetimeIndex", type(ts.index).__name__)

    result = generate_forecast(df, "Sales", "OrderDate", periods=3)
    n_hist = len(result.get("historical", []))
    if n_hist == rev_result["n_months"]:
        _pass(f"Forecast historical length ({n_hist}) == revenue_engine n_months")
    else:
        _fail("Forecast historical length mismatch",
              f"forecast_hist={n_hist}  engine_months={rev_result['n_months']}")

    if "period_context" in result:
        _pass("Forecast result contains period_context")
    else:
        _fail("Forecast result missing period_context")


# ---------------------------------------------------------------------------
# TEST 4 -- Currency Propagation (no hardcoded "$")
# ---------------------------------------------------------------------------

def test_4_currency_propagation():
    _section("TEST 4 -- Currency Propagation")

    test_cases = [
        ("USD via Currency col",    _make_df(currency="USD"),                        "USD"),
        ("INR via Currency col",    _make_df(currency="INR"),                        "INR"),
        ("GBP via Currency col",    _make_df(currency="GBP"),                        "GBP"),
        ("EUR via Currency col",    _make_df(currency="EUR"),                        "EUR"),
        ("Country=India => INR",    _make_df(currency=None, country="India"),        "INR"),
        ("Country=UnitedStates=>USD", _make_df(currency=None, country="United States"), "USD"),
    ]

    for name, df, expected_code in test_cases:
        detected = detect_currency(df)
        if detected.upper() == expected_code.upper():
            _pass(f"{name}: detected={detected}")
        else:
            _fail(f"{name}", f"expected={expected_code}  detected={detected}")

    # format_currency must not produce "$" for INR
    inr_val = format_currency(1_250_000, "INR")
    if "$" not in inr_val:
        _pass(f"format_currency(INR, 1.25M) = '{inr_val}' -- no hardcoded $")
    else:
        _fail("format_currency(INR) contains '$'", inr_val)

    # Revenue engine result must carry currency field
    df = _make_df(currency="EUR")
    result = compute_monthly_revenue(df, "OrderDate", "Sales")
    if result.get("currency"):
        _pass(f"compute_monthly_revenue result has currency='{result['currency']}'")
    else:
        _fail("compute_monthly_revenue result missing currency field")


# ---------------------------------------------------------------------------
# TEST 5 -- No Silent Failure
# ---------------------------------------------------------------------------

def test_5_no_silent_failure():
    _section("TEST 5 -- No Silent Failure")

    # A: insufficient periods (<2 months)
    df_1m = _make_df(n_months=1)
    try:
        result = compute_monthly_revenue(df_1m, "OrderDate", "Sales")
        if result["status"] in ("insufficient_data", "invalid"):
            _pass(f"1-month data => status='{result['status']}' (structured, not a crash)")
        else:
            _fail("1-month data should return insufficient_data", f"status={result['status']}")
    except Exception as e:
        _fail("1-month data caused exception", str(e))

    # B: null revenue column
    df_null = _make_df()
    df_null["Sales"] = None
    try:
        result = compute_monthly_revenue(df_null, "OrderDate", "Sales")
        if result["status"] in ("insufficient_data", "invalid"):
            _pass(f"Null revenue => status='{result['status']}' (graceful)")
        else:
            _fail("Null revenue should return error status", f"status={result['status']}")
    except Exception as e:
        _fail("Null revenue caused exception", str(e))

    # C: non-numeric revenue (coerce to NaN)
    df_text = _make_df(non_numeric=True)
    try:
        result = compute_monthly_revenue(df_text, "OrderDate", "Sales")
        if isinstance(result, dict) and "status" in result:
            _pass(f"Non-numeric revenue => status='{result['status']}' (graceful coercion)")
        else:
            _fail("Non-numeric revenue: unexpected result format")
    except Exception as e:
        _fail("Non-numeric revenue caused exception", str(e))

    # D: RCA with flat (0%) change -- should NOT crash
    flat_df = _make_df()
    flat_df["Sales"] = 100_000.0
    try:
        rca = analyze_root_causes(flat_df, "Sales")
        if isinstance(rca, dict) and "insight_summary" in rca:
            _pass("Flat revenue RCA returns structured response (no crash)")
        else:
            _fail("Flat revenue RCA: unexpected response format")
    except Exception as e:
        _fail("Flat revenue RCA caused exception", str(e))

    # E: forecast on 2 months -- must be gated
    df_2m = _make_df(n_months=2)
    result = generate_forecast(df_2m, "Sales", "OrderDate")
    if result.get("status") in ("invalid_forecast", "invalid", "error"):
        _pass(f"2-month forecast => status='{result['status']}' (gates enforced)")
    else:
        _fail("2-month forecast should be gated", f"status={result.get('status')}")


# ---------------------------------------------------------------------------
# TEST 6 -- Integrity Score is Data-Driven
# ---------------------------------------------------------------------------

def test_6_integrity_score():
    _section("TEST 6 -- Integrity Score is Data-Driven")

    # Good data: 24 months
    df_good = _make_df(n_months=24)
    rev_good = compute_monthly_revenue(df_good, "OrderDate", "Sales")
    score_good, quality_good, reasons_good = compute_integrity_score(rev_good, df_good, "Sales")

    if score_good >= 70:
        _pass(f"Good 24-month data => score={score_good} quality={quality_good}")
    else:
        _fail("Good data should score >= 70", f"score={score_good}")

    # Poor data: 1 month
    df_poor = _make_df(n_months=1)
    rev_poor = compute_monthly_revenue(df_poor, "OrderDate", "Sales")
    score_poor, quality_poor, reasons_poor = compute_integrity_score(rev_poor, df_poor, "Sales")

    if score_poor < score_good:
        _pass(f"1-month data => score={score_poor} < good_score={score_good} (penalty applied)")
    else:
        _fail("Poor data should score lower than good data",
              f"poor={score_poor}  good={score_good}")

    # Score must NOT be 95 (hardcoded sentinel)
    if score_good != 95:
        _pass(f"Integrity score is not hardcoded 95 (actual={score_good})")
    else:
        _fail("Score is exactly 95 -- likely hardcoded")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    # Disable AI narrative to ensure tests run deterministically (no Gemini API)
    os.environ["INSIGHTIQ_NO_AI"] = "1"

    print(f"\n{BOLD}InsightIQ -- Analytical Integrity Test Suite{RESET}")
    print("=" * 60)

    tests = [
        test_1_dashboard_vs_root_cause_match,
        test_2_period_comparison_consistency,
        test_3_forecast_input_integrity,
        test_4_currency_propagation,
        test_5_no_silent_failure,
        test_6_integrity_score,
    ]

    for test_fn in tests:
        try:
            test_fn()
        except Exception:
            global failed
            failed += 1
            print(f"  {RED}[ERROR]{RESET}  {test_fn.__name__}")
            traceback.print_exc()

    print(f"\n{'='*60}")
    total = passed + failed + skipped
    print(f"{BOLD}Results:{RESET}  "
          f"{GREEN}{passed} passed{RESET}  "
          f"{RED}{failed} failed{RESET}  "
          f"{YELLOW}{skipped} skipped{RESET}  "
          f"({total} total)")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
