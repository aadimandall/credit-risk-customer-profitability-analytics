"""
00_clean_raw_data.py

First step of the Credit Risk & Customer Profitability Analytics project.

This script loads the raw UCI credit card default Excel file, removes the extra
metadata/header row, standardizes the column names, runs basic data quality
checks, and creates borrower-level features used later for SQL analysis,
modeling, validation, and Tableau reporting.

I keep this step separate because the rest of the project depends on having one
clean, reproducible customer-level dataset.
"""

from pathlib import Path
from datetime import datetime
import json
import logging

import numpy as np
import pandas as pd

# Project paths

BASE = Path(__file__).resolve().parents[1]

RAW_FILE = BASE / "data" / "raw" / "default_of_credit_card_clients.xls"
PROCESSED_DIR = BASE / "data" / "processed"

CLEAN_FILE = PROCESSED_DIR / "credit_card_default_clean.csv"
ANALYSIS_READY_FILE = PROCESSED_DIR / "credit_card_default_analysis_ready.csv"

QUALITY_REPORT_TXT = PROCESSED_DIR / "data_quality_report.txt"
QUALITY_REPORT_JSON = PROCESSED_DIR / "data_quality_report.json"
SCHEMA_REPORT_FILE = PROCESSED_DIR / "schema_report.csv"
TARGET_DISTRIBUTION_FILE = PROCESSED_DIR / "target_distribution.csv"
MISSING_VALUES_FILE = PROCESSED_DIR / "missing_values_report.csv"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Column mapping

RAW_TO_CLEAN_COLUMNS = {
    "ID": "customer_id",
    "LIMIT_BAL": "credit_limit",
    "SEX": "sex",
    "EDUCATION": "education",
    "MARRIAGE": "marriage",
    "AGE": "age",
    "PAY_0": "repay_status_sep",
    "PAY_2": "repay_status_aug",
    "PAY_3": "repay_status_jul",
    "PAY_4": "repay_status_jun",
    "PAY_5": "repay_status_may",
    "PAY_6": "repay_status_apr",
    "BILL_AMT1": "bill_amt_sep",
    "BILL_AMT2": "bill_amt_aug",
    "BILL_AMT3": "bill_amt_jul",
    "BILL_AMT4": "bill_amt_jun",
    "BILL_AMT5": "bill_amt_may",
    "BILL_AMT6": "bill_amt_apr",
    "PAY_AMT1": "pay_amt_sep",
    "PAY_AMT2": "pay_amt_aug",
    "PAY_AMT3": "pay_amt_jul",
    "PAY_AMT4": "pay_amt_jun",
    "PAY_AMT5": "pay_amt_may",
    "PAY_AMT6": "pay_amt_apr",
    "default payment next month": "default_payment_next_month"
}

BASE_COLUMNS = list(RAW_TO_CLEAN_COLUMNS.values())
TARGET_COL = "default_payment_next_month"

REPAYMENT_STATUS_COLS = [
    "repay_status_sep",
    "repay_status_aug",
    "repay_status_jul",
    "repay_status_jun",
    "repay_status_may",
    "repay_status_apr"
]

BILL_AMOUNT_COLS = [
    "bill_amt_sep",
    "bill_amt_aug",
    "bill_amt_jul",
    "bill_amt_jun",
    "bill_amt_may",
    "bill_amt_apr"
]

PAYMENT_AMOUNT_COLS = [
    "pay_amt_sep",
    "pay_amt_aug",
    "pay_amt_jul",
    "pay_amt_jun",
    "pay_amt_may",
    "pay_amt_apr"
]


def load_raw_dataset(file_path: Path) -> pd.DataFrame:
    """Load the raw Excel dataset and skip the first UCI metadata header row."""
    if not file_path.exists():
        raise FileNotFoundError(
            f"Raw file not found: {file_path}\n"
            "Make sure the file is saved in data/raw/ and named exactly:\n"
            "default_of_credit_card_clients.xls"
        )

    logging.info("Loading raw dataset...")
    # The UCI Excel file includes an extra title/header row, so header=1 is required.
    df_raw = pd.read_excel(file_path, header=1) 
    df_raw.columns = df_raw.columns.astype(str).str.strip()

    return df_raw


def clean_column_names(df_raw: pd.DataFrame) -> pd.DataFrame:
    """Rename raw dataset columns and keep only expected project columns."""
    missing_raw_columns = [
        col for col in RAW_TO_CLEAN_COLUMNS.keys()
        if col not in df_raw.columns
    ]

    if missing_raw_columns:
        raise ValueError(
            f"Missing expected raw columns: {missing_raw_columns}"
        )

    df_clean = df_raw.rename(columns=RAW_TO_CLEAN_COLUMNS)
    # Keep only the expected fields so later scripts do not depend on accidental columns.
    df_clean = df_clean[BASE_COLUMNS].copy()

    # Convert all project columns to numeric where possible
    for col in BASE_COLUMNS:
        df_clean[col] = pd.to_numeric(df_clean[col], errors="coerce")

    return df_clean


def validate_clean_dataset(df: pd.DataFrame) -> dict:
    """Run data quality checks and return report dictionary."""
    logging.info("Running data quality checks...")

    warnings = []

    row_count = int(df.shape[0])
    column_count = int(df.shape[1])
    duplicate_customer_ids = int(df["customer_id"].duplicated().sum())

    if row_count != 30000:
        warnings.append(f"Expected 30,000 rows, but found {row_count}.")

    if column_count != 25:
        warnings.append(f"Expected 25 columns, but found {column_count}.")

    if duplicate_customer_ids > 0:
        warnings.append(f"Found {duplicate_customer_ids} duplicate customer IDs.")

    target_values = sorted(df[TARGET_COL].dropna().unique().tolist())

    if set(target_values) != {0, 1}:
        raise ValueError(
            f"Unexpected target values found: {target_values}. "
            "Expected only 0 and 1."
        )

    invalid_credit_limits = int((df["credit_limit"] <= 0).sum())
    invalid_ages = int(((df["age"] < 18) | (df["age"] > 100)).sum())

    if invalid_credit_limits > 0:
        warnings.append(f"Found {invalid_credit_limits} rows with non-positive credit limits.")

    if invalid_ages > 0:
        warnings.append(f"Found {invalid_ages} rows with unusual ages outside 18-100.")

    missing_values = {
        col: int(value)
        for col, value in df.isna().sum().items()
    }

    target_counts = {
        str(int(index)): int(value)
        for index, value in df[TARGET_COL].value_counts().sort_index().items()
    }

    target_percentages = {
        str(int(index)): round(float(value), 4)
        for index, value in df[TARGET_COL].value_counts(normalize=True).sort_index().items()
    }

    report = {
        "project": "Credit Risk & Customer Profitability Analytics",
        "script": "00_clean_raw_data.py",
        "run_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_file": str(RAW_FILE),
        "clean_output_file": str(CLEAN_FILE),
        "analysis_ready_output_file": str(ANALYSIS_READY_FILE),
        "row_count": row_count,
        "column_count": column_count,
        "duplicate_customer_ids": duplicate_customer_ids,
        "missing_values": missing_values,
        "target_counts": target_counts,
        "target_percentages": target_percentages,
        "validation_warnings": warnings
    }

    return report


def add_business_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create analysis-ready features for SQL, Python modeling, and Tableau.

    These features are based only on borrower information available before
    the default outcome, which helps avoid target leakage.
    """
    logging.info("Creating business features...")

    df_features = df.copy()

    # Readable category labels
    df_features["sex_label"] = df_features["sex"].map({
        1: "Male",
        2: "Female"
    }).fillna("Unknown")

    df_features["education_label"] = df_features["education"].map({
        1: "Graduate school",
        2: "University",
        3: "High school",
        4: "Other",
        5: "Unknown",
        6: "Unknown",
        0: "Unknown"
    }).fillna("Unknown")

    df_features["marriage_label"] = df_features["marriage"].map({
        1: "Married",
        2: "Single",
        3: "Other",
        0: "Unknown"
    }).fillna("Unknown")

    # Age segmentation
    df_features["age_group"] = pd.cut(
        df_features["age"],
        bins=[0, 24, 34, 44, 54, 100],
        labels=["Under 25", "25-34", "35-44", "45-54", "55+"],
        include_lowest=True
    ).astype("object").fillna("Unknown")

    # Credit limit segmentation
    df_features["credit_limit_segment"] = pd.cut(
        df_features["credit_limit"],
        bins=[-np.inf, 49999, 199999, 499999, np.inf],
        labels=["Low limit", "Mid limit", "High limit", "Very high limit"]
    ).astype("object").fillna("Unknown")

    # Repayment behavior features
    df_features["max_repayment_delay"] = df_features[REPAYMENT_STATUS_COLS].max(axis=1)
    df_features["avg_repayment_status"] = df_features[REPAYMENT_STATUS_COLS].mean(axis=1)
    df_features["months_with_payment_delay"] = df_features[REPAYMENT_STATUS_COLS].ge(1).sum(axis=1)
    df_features["months_with_serious_delay"] = df_features[REPAYMENT_STATUS_COLS].ge(2).sum(axis=1)

    df_features["any_payment_delay_flag"] = (
        df_features["months_with_payment_delay"] > 0
    ).astype(int)

    df_features["serious_payment_delay_flag"] = (
        df_features["months_with_serious_delay"] > 0
    ).astype(int)

    # Balance and payment behavior features
    df_features["avg_bill_amount"] = df_features[BILL_AMOUNT_COLS].mean(axis=1)
    df_features["avg_payment_amount"] = df_features[PAYMENT_AMOUNT_COLS].mean(axis=1)
    # Utilization is only a proxy because this public dataset does not include full account economics.
    df_features["utilization_proxy"] = (
        df_features["bill_amt_sep"] / df_features["credit_limit"].replace(0, np.nan)
    )

    df_features["utilization_segment"] = pd.cut(
        df_features["utilization_proxy"],
        bins=[-np.inf, 0, 0.25, 0.75, 1.0, np.inf],
        labels=[
            "Negative or zero balance",
            "Low utilization",
            "Medium utilization",
            "High utilization",
            "Over limit / very high utilization"
        ]
    ).astype("object").fillna("Unknown")

    df_features["recent_payment_to_bill_ratio"] = (
        df_features["pay_amt_sep"] /
        df_features["bill_amt_aug"].replace(0, np.nan)
    )

    df_features["recent_payment_to_bill_ratio"] = (
        df_features["recent_payment_to_bill_ratio"]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0)
    )

    # Quartile-style segments for dashboarding
    df_features["bill_statement_size_segment"] = pd.qcut(
        df_features["avg_bill_amount"].rank(method="first"),
        q=4,
        labels=["Small bill", "Medium bill", "Large bill", "Very large bill"]
    )

    df_features["payment_amount_segment"] = pd.qcut(
        df_features["avg_payment_amount"].rank(method="first"),
        q=4,
        labels=["Low payment", "Medium payment", "High payment", "Very high payment"]
    )

    # Business-friendly repayment category
    conditions = [
        df_features["months_with_serious_delay"] >= 2,
        df_features["months_with_serious_delay"] == 1,
        df_features["months_with_payment_delay"] >= 1,
        df_features["recent_payment_to_bill_ratio"] >= 0.50,
        df_features["pay_amt_sep"] > 0
    ]

    choices = [
        "Repeated serious delay",
        "Recent serious delay",
        "Minor payment delay",
        "Strong recent repayment",
        "Partial recent repayment"
    ]

    df_features["repayment_behavior_category"] = np.select(
        conditions,
        choices,
        default="No recent payment or low activity"
    )

    # Simple portfolio monitoring flag
    df_features["portfolio_monitoring_flag"] = np.where(
        (df_features["serious_payment_delay_flag"] == 1) |
        (df_features["utilization_proxy"] >= 0.90),
        1,
        0
    )

    return df_features


def create_schema_report(df: pd.DataFrame) -> pd.DataFrame:
    """Create a column-level schema and profiling report."""
    schema_rows = []

    for col in df.columns:
        series = df[col]

        row = {
            "column_name": col,
            "dtype": str(series.dtype),
            "missing_count": int(series.isna().sum()),
            "missing_pct": round(float(series.isna().mean()), 4),
            "unique_count": int(series.nunique(dropna=True))
        }

        if pd.api.types.is_numeric_dtype(series):
            row["min"] = float(series.min()) if not series.dropna().empty else None
            row["max"] = float(series.max()) if not series.dropna().empty else None
            row["mean"] = float(series.mean()) if not series.dropna().empty else None
        else:
            row["min"] = None
            row["max"] = None
            row["mean"] = None

        schema_rows.append(row)

    return pd.DataFrame(schema_rows)


def save_reports(df_clean: pd.DataFrame, df_analysis_ready: pd.DataFrame, report: dict) -> None:
    """Save quality, schema, missing value, and target distribution reports."""
    logging.info("Saving reports...")

    # Save JSON report
    with open(QUALITY_REPORT_JSON, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    # Save readable text report
    readable_report = f"""
Credit Risk & Customer Profitability Analytics
Data Quality Report

Run timestamp:
{report["run_timestamp"]}

Source file:
{report["source_file"]}

Clean output file:
{report["clean_output_file"]}

Analysis-ready output file:
{report["analysis_ready_output_file"]}

Dataset shape:
Rows: {report["row_count"]}
Columns: {report["column_count"]}

Duplicate customer IDs:
{report["duplicate_customer_ids"]}

Target distribution:
{json.dumps(report["target_counts"], indent=4)}

Target percentages:
{json.dumps(report["target_percentages"], indent=4)}

Validation warnings:
{json.dumps(report["validation_warnings"], indent=4)}

Missing values:
{json.dumps(report["missing_values"], indent=4)}
"""

    QUALITY_REPORT_TXT.write_text(readable_report, encoding="utf-8")

    # Save schema report
    schema_report = create_schema_report(df_analysis_ready)
    schema_report.to_csv(SCHEMA_REPORT_FILE, index=False)

    # Save missing values report
    missing_values_report = (
        df_clean.isna()
        .sum()
        .reset_index()
        .rename(columns={"index": "column_name", 0: "missing_count"})
    )
    missing_values_report["missing_pct"] = (
        missing_values_report["missing_count"] / len(df_clean)
    ).round(4)

    missing_values_report.to_csv(MISSING_VALUES_FILE, index=False)

    # Save target distribution
    target_distribution = (
        df_clean[TARGET_COL]
        .value_counts()
        .sort_index()
        .reset_index()
    )
    target_distribution.columns = ["default_payment_next_month", "customer_count"]
    target_distribution["percentage"] = (
        target_distribution["customer_count"] / len(df_clean)
    ).round(4)

    target_distribution.to_csv(TARGET_DISTRIBUTION_FILE, index=False)


def main() -> None:
    logging.info("Starting raw data cleaning pipeline...")

    df_raw = load_raw_dataset(RAW_FILE)
    df_clean = clean_column_names(df_raw)
    quality_report = validate_clean_dataset(df_clean)
    df_analysis_ready = add_business_features(df_clean)

    # Save cleaned datasets
    df_clean.to_csv(CLEAN_FILE, index=False)
    df_analysis_ready.to_csv(ANALYSIS_READY_FILE, index=False)

    # Save reports
    save_reports(df_clean, df_analysis_ready, quality_report)

    logging.info("Cleaning pipeline completed successfully.")

    print("=" * 80)
    print("Credit Risk & Customer Profitability Analytics")
    print("Raw data cleaning completed successfully.")
    print("=" * 80)

    print(f"\nClean base dataset saved to:\n{CLEAN_FILE}")
    print(f"\nAnalysis-ready dataset saved to:\n{ANALYSIS_READY_FILE}")
    print(f"\nData quality report saved to:\n{QUALITY_REPORT_TXT}")
    print(f"\nSchema report saved to:\n{SCHEMA_REPORT_FILE}")

    print("\nDataset shape:")
    print(df_clean.shape)

    print("\nTarget distribution:")
    print(df_clean[TARGET_COL].value_counts().sort_index())

    print("\nTarget percentage:")
    print(df_clean[TARGET_COL].value_counts(normalize=True).sort_index())

    print("\nAnalysis-ready preview:")
    print(df_analysis_ready.head())


if __name__ == "__main__":
    main()
