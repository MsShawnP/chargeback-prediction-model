"""
U1 EDA -- Profile Cinderhaven tables and verify data sufficiency before modeling.

Prerequisites:
  1. flyctl proxy 5432 -a cinderhaven-data-platform
  2. DATABASE_URL set (via .env or export)

Run from project root:
  python src/pipeline/eda.py

Writes CSVs to output/frames/eda_*.csv for reference.
Update HANDOFF.md with findings before proceeding to U2.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.pipeline.db import query_to_df  # noqa: E402

OUTPUT = Path("output/frames")

EXPECTED_ROW_RANGES = {
    "raw.retailer_chargebacks": (300, 700),
    "raw.retailer_deductions": (1000, 3000),
    "raw.retailer_shipments": (5000, 10000),
    "raw.product_master": (20, 50),
    "raw.distribution_log": (10, 1000),
    "raw.retailer_deduction_codes": (5, 100),
}


def _section(title: str) -> None:
    print(f"\n{'=' * 52}")
    print(f"  {title}")
    print("=" * 52)


def profile_row_counts() -> pd.DataFrame:
    _section("Row Counts")
    rows = []
    for table, (lo, hi) in EXPECTED_ROW_RANGES.items():
        try:
            n = int(query_to_df(f"SELECT COUNT(*) AS n FROM {table}").iloc[0]["n"])
            flag = "" if lo <= n <= hi else f"  !!  EXPECTED {lo:,}–{hi:,}"
            print(f"  {table:<35} {n:>7,}{flag}")
            rows.append({"table": table, "row_count": n, "in_expected_range": lo <= n <= hi})
        except Exception as exc:
            print(f"  {table:<35} ERROR: {exc}")
            rows.append({"table": table, "row_count": -1, "in_expected_range": False})
    return pd.DataFrame(rows)


def profile_date_ranges() -> None:
    _section("Date Ranges")
    probes = [
        ("raw.retailer_shipments", "ship_date"),
        ("raw.retailer_chargebacks", "chargeback_date"),
    ]
    for table, col in probes:
        try:
            r = query_to_df(
                f"SELECT MIN({col}) AS min_date, MAX({col}) AS max_date FROM {table}"
            ).iloc[0]
            print(f"  {table}.{col}: {r['min_date']} -> {r['max_date']}")
        except Exception as exc:
            print(f"  {table}.{col}: ERROR {exc}")


def profile_product_master_nulls() -> pd.DataFrame:
    _section("Product Master -- Schema and Null Rates")
    try:
        cols_df = query_to_df("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'raw' AND table_name = 'product_master'
            ORDER BY ordinal_position
        """)
        all_cols = cols_df["column_name"].tolist()
        print(f"  Columns: {', '.join(all_cols)}\n")
    except Exception as exc:
        print(f"  Could not read schema: {exc}")
        return pd.DataFrame()

    # Profile columns likely to represent data quality flags
    target_cols = [
        c for c in all_cols
        if any(k in c.lower() for k in ["gtin", "upc", "case", "weight", "dim", "length"])
    ]
    if not target_cols:
        print("  No data-quality columns identified -- check schema manually.")
        return pd.DataFrame()

    try:
        total = int(query_to_df("SELECT COUNT(*) AS n FROM raw.product_master").iloc[0]["n"])
    except Exception as exc:
        print(f"  Could not count product_master rows: {exc}")
        return pd.DataFrame()

    rows = []
    for col in target_cols:
        try:
            n_null = int(
                query_to_df(
                    f"SELECT COUNT(*) AS n FROM raw.product_master WHERE {col} IS NULL"
                ).iloc[0]["n"]
            )
            pct = n_null / total if total > 0 else 0.0
            print(f"  {col:<30} {n_null}/{total} ({pct:.1%}) null")
            rows.append({"column": col, "null_count": n_null, "total": total, "null_pct": pct})
        except Exception as exc:
            print(f"  {col}: ERROR {exc}")
    return pd.DataFrame(rows)


def check_chargeback_shipment_join() -> dict:
    _section("Chargeback -> Shipment Join Rate (key U4 prerequisite)")
    try:
        total = int(
            query_to_df("SELECT COUNT(*) AS n FROM raw.retailer_chargebacks").iloc[0]["n"]
        )
    except Exception as exc:
        print(f"  Could not count retailer_chargebacks: {exc}")
        return {}

    result = {"total_chargebacks": total}

    # Attempt 1: direct order_id join
    try:
        matched = int(query_to_df("""
            SELECT COUNT(*) AS n
            FROM raw.retailer_chargebacks c
            JOIN raw.retailer_shipments s ON c.order_id = s.order_id
        """).iloc[0]["n"])
        rate = matched / total if total > 0 else 0.0
        result["order_id_matched"] = matched
        result["order_id_rate"] = round(rate, 3)
        print(f"  order_id join:        {matched:,}/{total:,} = {rate:.1%}")
        if rate >= 0.5:
            print("  OK Match rate ≥ 50% -- U4 can use order_id join")
        else:
            print("  !!  Match rate < 50% -- evaluate date-window fallback")
    except Exception as exc:
        print(f"  order_id join failed: {exc}")
        result["order_id_error"] = str(exc)

    # Attempt 2: retailer_id + sku + 90-day window (fallback / cross-check)
    try:
        matched_w = int(query_to_df("""
            SELECT COUNT(*) AS n
            FROM raw.retailer_chargebacks c
            JOIN raw.retailer_shipments s
              ON c.retailer_id = s.retailer_id
             AND c.sku         = s.sku
             AND c.chargeback_date BETWEEN s.ship_date
                                       AND s.ship_date + INTERVAL '90 days'
        """).iloc[0]["n"])
        rate_w = matched_w / total if total > 0 else 0.0
        result["window_matched"] = matched_w
        result["window_rate"] = round(rate_w, 3)
        print(f"  date-window join:     {matched_w:,}/{total:,} = {rate_w:.1%}")
        if rate_w >= 0.5:
            print("  OK Window join ≥ 50% -- viable fallback if order_id join is weak")
    except Exception as exc:
        print(f"  Date-window join failed: {exc}")
        result["window_error"] = str(exc)

    return result


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 52)
    print("  Cinderhaven EDA -- U1 Data Sufficiency Check")
    print("=" * 52)

    counts_df = profile_row_counts()
    counts_df.to_csv(OUTPUT / "eda_row_counts.csv", index=False)

    profile_date_ranges()

    nulls_df = profile_product_master_nulls()
    if not nulls_df.empty:
        nulls_df.to_csv(OUTPUT / "eda_product_master_nulls.csv", index=False)

    join_stats = check_chargeback_shipment_join()
    pd.DataFrame([join_stats]).to_csv(OUTPUT / "eda_join_stats.csv", index=False)

    print(f"\n-> Outputs written to {OUTPUT}/")
    print("-> Update HANDOFF.md with findings before proceeding to U2\n")


if __name__ == "__main__":
    main()
