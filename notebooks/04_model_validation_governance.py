"""
04_model_validation_governance.py

Validation and governance layer for the Credit Risk & Customer Profitability
Analytics project.

This script takes the scored customer file from 03_credit_risk_model.py and
checks whether the model is useful as a portfolio risk-ranking and decision-support
tool. I evaluate calibration, risk-decile lift, threshold tradeoffs, segment behavior,
fairness-monitoring indicators, error types, and business impact.

I added this layer because a credit-risk project should not stop at ROC-AUC.
The model needs to show whether it ranks borrowers well, separates high-risk
customers from low-risk customers, supports a defensible operating threshold,
and creates outputs that can be monitored by a risk or portfolio strategy team.

This is a portfolio analytics and governance demonstration, not a production
credit-decisioning system.
"""

from pathlib import Path
from datetime import datetime
import json
import logging

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]

SCORED_CUSTOMERS_FILE = (
    BASE
    / "data"
    / "processed"
    / "model_outputs"
    / "credit_risk_scored_customers.csv"
)

MODEL_METRICS_FILE = (
    BASE
    / "data"
    / "processed"
    / "model_outputs"
    / "model_metrics.json"
)

OUTPUT_DIR = BASE / "data" / "processed" / "validation_outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

VALIDATION_SUMMARY_FILE = OUTPUT_DIR / "model_validation_summary.csv"
CALIBRATION_FILE = OUTPUT_DIR / "calibration_by_probability_band.csv"
RISK_DECILE_FILE = OUTPUT_DIR / "risk_decile_business_summary.csv"
THRESHOLD_BUSINESS_FILE = OUTPUT_DIR / "threshold_business_impact.csv"
SEGMENT_MONITORING_FILE = OUTPUT_DIR / "segment_model_monitoring.csv"
FAIRNESS_MONITORING_FILE = OUTPUT_DIR / "fairness_monitoring_summary.csv"
ERROR_ANALYSIS_FILE = OUTPUT_DIR / "model_error_analysis.csv"
GOVERNANCE_CHECKLIST_FILE = OUTPUT_DIR / "model_governance_checklist.csv"
EXECUTIVE_VALIDATION_SUMMARY_FILE = OUTPUT_DIR / "_executive_validation_governance_summary.md"

TARGET = "default_payment_next_month"
PREDICTION_COL = "predicted_default_probability"
#Proxy assumptions used only for validation and portfolio impact analysis.
#The public dataset does not include true LGD, recoveries, charge-offs, or revenue.
LGD_ASSUMPTION = 0.60
SIX_MONTH_REVENUE_RATE_PROXY = 0.09
MIN_SEGMENT_SIZE = 100

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def validate_inputs() -> None:
    if not SCORED_CUSTOMERS_FILE.exists():
        raise FileNotFoundError(
            f"Missing scored customer file: {SCORED_CUSTOMERS_FILE}\n"
            "Run notebooks/03_credit_risk_model.py first."
        )

    if not MODEL_METRICS_FILE.exists():
        logging.warning(
            "Model metrics file not found. The script will still run using scored customers."
        )


def load_scored_customers() -> pd.DataFrame:
    logging.info("Loading scored customer file...")

    df = pd.read_csv(SCORED_CUSTOMERS_FILE)

    required_columns = [TARGET, PREDICTION_COL]
    missing_columns = [col for col in required_columns if col not in df.columns]

    if missing_columns:
        raise ValueError(
            f"Missing required columns in scored customer file: {missing_columns}"
        )

    df = df.copy()

    df[TARGET] = df[TARGET].astype(int)
    df[PREDICTION_COL] = df[PREDICTION_COL].clip(0, 1)

    if "balance_exposure_proxy" not in df.columns:
        if "avg_bill_amount" in df.columns:
            df["balance_exposure_proxy"] = df["avg_bill_amount"].clip(lower=0)
        elif "bill_amt_sep" in df.columns:
            df["balance_exposure_proxy"] = df["bill_amt_sep"].clip(lower=0)
        else:
            df["balance_exposure_proxy"] = 0.0

    if "predicted_expected_loss_proxy" not in df.columns:
        df["predicted_expected_loss_proxy"] = (
            df[PREDICTION_COL]
            * df["balance_exposure_proxy"]
            * LGD_ASSUMPTION
        )

    if "predicted_revenue_proxy_6mo" not in df.columns:
        df["predicted_revenue_proxy_6mo"] = (
            df["balance_exposure_proxy"]
            * SIX_MONTH_REVENUE_RATE_PROXY
        )

    if "predicted_risk_adjusted_profit_proxy" not in df.columns:
        df["predicted_risk_adjusted_profit_proxy"] = (
            df["predicted_revenue_proxy_6mo"]
            - df["predicted_expected_loss_proxy"]
        )

    if "predicted_default_risk_decile" not in df.columns:
        df["predicted_default_risk_decile"] = pd.qcut(
            df[PREDICTION_COL].rank(method="first"),
            q=10,
            labels=False,
        )
        df["predicted_default_risk_decile"] = (
            10 - df["predicted_default_risk_decile"]
        )

    df["actual_loss_proxy"] = (
        df[TARGET]
        * df["balance_exposure_proxy"]
        * LGD_ASSUMPTION
    )

    df["actual_risk_adjusted_profit_proxy"] = (
        df["predicted_revenue_proxy_6mo"]
        - df["actual_loss_proxy"]
    )

    return df


def safe_divide(numerator: float, denominator: float) -> float:
    if denominator == 0 or pd.isna(denominator):
        return np.nan
    return numerator / denominator


def create_validation_summary(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Creating validation summary...")

    y = df[TARGET]
    p = df[PREDICTION_COL]
    # are close to the observed default rate, not just whether the ranking is good.
    brier_score = float(np.mean((p - y) ** 2))
    portfolio_default_rate = float(y.mean())
    avg_predicted_pd = float(p.mean())
    calibration_gap = avg_predicted_pd - portfolio_default_rate

    top_decile = df[df["predicted_default_risk_decile"] == 1]
    bottom_decile = df[df["predicted_default_risk_decile"] == 10]

    top_decile_default_rate = float(top_decile[TARGET].mean())
    bottom_decile_default_rate = float(bottom_decile[TARGET].mean())

    top_bottom_separation = top_decile_default_rate - bottom_decile_default_rate
    lift_top_decile = safe_divide(
        top_decile_default_rate,
        portfolio_default_rate,
    )

    summary = pd.DataFrame(
        [
            {
                "record_count": len(df),
                "portfolio_default_rate": portfolio_default_rate,
                "avg_predicted_default_probability": avg_predicted_pd,
                "calibration_gap": calibration_gap,
                "absolute_calibration_gap": abs(calibration_gap),
                "brier_score": brier_score,
                "top_decile_default_rate": top_decile_default_rate,
                "bottom_decile_default_rate": bottom_decile_default_rate,
                "top_bottom_default_rate_separation": top_bottom_separation,
                "top_decile_lift_vs_portfolio": lift_top_decile,
                "total_predicted_expected_loss_proxy": df[
                    "predicted_expected_loss_proxy"
                ].sum(),
                "total_actual_loss_proxy": df["actual_loss_proxy"].sum(),
                "total_predicted_revenue_proxy_6mo": df[
                    "predicted_revenue_proxy_6mo"
                ].sum(),
                "total_predicted_risk_adjusted_profit_proxy": df[
                    "predicted_risk_adjusted_profit_proxy"
                ].sum(),
                "total_actual_risk_adjusted_profit_proxy": df[
                    "actual_risk_adjusted_profit_proxy"
                ].sum(),
            }
        ]
    )

    numeric_cols = summary.select_dtypes(include=[np.number]).columns
    summary[numeric_cols] = summary[numeric_cols].round(6)

    return summary


def create_calibration_table(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Creating calibration table...")

    calibration_df = df[[TARGET, PREDICTION_COL, "balance_exposure_proxy"]].copy()

    calibration_df["probability_band"] = pd.qcut(
        calibration_df[PREDICTION_COL].rank(method="first"),
        q=10,
        labels=[
            "01_Lowest risk",
            "02",
            "03",
            "04",
            "05",
            "06",
            "07",
            "08",
            "09",
            "10_Highest risk",
        ],
    )

    band_summary = (
        calibration_df.groupby("probability_band", observed=False)
        .agg(
            customer_count=(TARGET, "size"),
            defaulted_customers=(TARGET, "sum"),
            observed_default_rate=(TARGET, "mean"),
            avg_predicted_default_probability=(PREDICTION_COL, "mean"),
            min_predicted_default_probability=(PREDICTION_COL, "min"),
            max_predicted_default_probability=(PREDICTION_COL, "max"),
            total_balance_exposure_proxy=("balance_exposure_proxy", "sum"),
        )
        .reset_index()
    )

    band_summary["calibration_gap"] = (
        band_summary["avg_predicted_default_probability"]
        - band_summary["observed_default_rate"]
    )

    band_summary["absolute_calibration_gap"] = band_summary[
        "calibration_gap"
    ].abs()

    numeric_cols = band_summary.select_dtypes(include=[np.number]).columns
    band_summary[numeric_cols] = band_summary[numeric_cols].round(6)

    return band_summary

# Risk deciles show whether the model concentrates defaults and losses
# in the highest-risk borrower groups.
def create_risk_decile_business_summary(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Creating risk decile business summary...")

    portfolio_default_rate = df[TARGET].mean()
    total_defaults = df[TARGET].sum()
    total_actual_loss = df["actual_loss_proxy"].sum()

    decile_summary = (
        df.groupby("predicted_default_risk_decile", as_index=False)
        .agg(
            customer_count=(TARGET, "size"),
            defaulted_customers=(TARGET, "sum"),
            observed_default_rate=(TARGET, "mean"),
            avg_predicted_default_probability=(PREDICTION_COL, "mean"),
            min_predicted_default_probability=(PREDICTION_COL, "min"),
            max_predicted_default_probability=(PREDICTION_COL, "max"),
            total_balance_exposure_proxy=("balance_exposure_proxy", "sum"),
            total_predicted_expected_loss_proxy=(
                "predicted_expected_loss_proxy",
                "sum",
            ),
            total_actual_loss_proxy=("actual_loss_proxy", "sum"),
            total_predicted_revenue_proxy_6mo=(
                "predicted_revenue_proxy_6mo",
                "sum",
            ),
            total_predicted_risk_adjusted_profit_proxy=(
                "predicted_risk_adjusted_profit_proxy",
                "sum",
            ),
            total_actual_risk_adjusted_profit_proxy=(
                "actual_risk_adjusted_profit_proxy",
                "sum",
            ),
        )
        .sort_values("predicted_default_risk_decile", ascending=True)
    )

    decile_summary["portfolio_default_rate"] = portfolio_default_rate
    decile_summary["lift_vs_portfolio"] = (
        decile_summary["observed_default_rate"]
        / portfolio_default_rate
    )

    decile_summary["default_capture_rate"] = (
        decile_summary["defaulted_customers"]
        / total_defaults
    )

    decile_summary["actual_loss_capture_rate"] = (
        decile_summary["total_actual_loss_proxy"]
        / total_actual_loss
    )

    decile_summary["cumulative_default_capture_rate"] = decile_summary[
        "default_capture_rate"
    ].cumsum()

    decile_summary["cumulative_actual_loss_capture_rate"] = decile_summary[
        "actual_loss_capture_rate"
    ].cumsum()

    numeric_cols = decile_summary.select_dtypes(include=[np.number]).columns
    decile_summary[numeric_cols] = decile_summary[numeric_cols].round(6)

    return decile_summary


def create_threshold_business_impact(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Creating threshold business-impact table...")

    rows = []
    portfolio_default_rate = df[TARGET].mean()

    for threshold in np.arange(0.05, 0.81, 0.025):
        working = df.copy()
        working["policy_decision"] = np.where(
            working[PREDICTION_COL] >= threshold,
            "Review_or_Decline",
            "Approve",
        )

        approved = working[working["policy_decision"] == "Approve"]
        flagged = working[working["policy_decision"] == "Review_or_Decline"]

        approved_default_rate = (
            approved[TARGET].mean() if len(approved) > 0 else np.nan
        )

        flagged_default_rate = (
            flagged[TARGET].mean() if len(flagged) > 0 else np.nan
        )

        rows.append(
            {
                "threshold": round(float(threshold), 3),
                "approved_customers": len(approved),
                "flagged_customers": len(flagged),
                "approval_rate": safe_divide(len(approved), len(working)),
                "flag_rate": safe_divide(len(flagged), len(working)),
                "approved_observed_default_rate": approved_default_rate,
                "flagged_observed_default_rate": flagged_default_rate,
                "approved_avg_predicted_pd": (
                    approved[PREDICTION_COL].mean()
                    if len(approved) > 0
                    else np.nan
                ),
                "flagged_avg_predicted_pd": (
                    flagged[PREDICTION_COL].mean()
                    if len(flagged) > 0
                    else np.nan
                ),
                "approved_balance_exposure_proxy": approved[
                    "balance_exposure_proxy"
                ].sum(),
                "flagged_balance_exposure_proxy": flagged[
                    "balance_exposure_proxy"
                ].sum(),
                "approved_predicted_expected_loss_proxy": approved[
                    "predicted_expected_loss_proxy"
                ].sum(),
                "flagged_predicted_expected_loss_proxy": flagged[
                    "predicted_expected_loss_proxy"
                ].sum(),
                "approved_predicted_revenue_proxy_6mo": approved[
                    "predicted_revenue_proxy_6mo"
                ].sum(),
                "approved_predicted_risk_adjusted_profit_proxy": approved[
                    "predicted_risk_adjusted_profit_proxy"
                ].sum(),
                "approved_actual_loss_proxy": approved[
                    "actual_loss_proxy"
                ].sum(),
                "flagged_actual_loss_proxy": flagged[
                    "actual_loss_proxy"
                ].sum(),
                "historical_defaults_captured_by_flag": flagged[
                    TARGET
                ].sum(),
                "historical_default_capture_rate": safe_divide(
                    flagged[TARGET].sum(),
                    working[TARGET].sum(),
                ),
                "portfolio_default_rate": portfolio_default_rate,
            }
        )

    threshold_df = pd.DataFrame(rows)

    threshold_df["threshold_policy_label"] = np.select(
        [
            (threshold_df["approval_rate"] >= 0.70)
            & (
                threshold_df["approved_observed_default_rate"]
                <= threshold_df["portfolio_default_rate"]
            ),
            (threshold_df["approval_rate"] >= 0.50)
            & (
                threshold_df["approved_observed_default_rate"]
                <= threshold_df["portfolio_default_rate"]
            ),
            threshold_df["approval_rate"] < 0.50,
        ],
        [
            "Growth-capable threshold",
            "Balanced threshold",
            "Likely too restrictive",
        ],
        default="Higher-risk approval threshold",
    )

    threshold_df["meets_balanced_policy_guardrail"] = (
        (threshold_df["approval_rate"] >= 0.50)
        & (
            threshold_df["approved_observed_default_rate"]
            <= threshold_df["portfolio_default_rate"]
        )
    ).astype(int)

    numeric_cols = threshold_df.select_dtypes(include=[np.number]).columns
    threshold_df[numeric_cols] = threshold_df[numeric_cols].round(6)

    return threshold_df


def choose_recommended_threshold(threshold_df: pd.DataFrame) -> pd.Series:
    eligible = threshold_df[
        threshold_df["meets_balanced_policy_guardrail"] == 1
    ].copy()

    if eligible.empty:
        return threshold_df.sort_values(
            "approved_predicted_risk_adjusted_profit_proxy",
            ascending=False,
        ).iloc[0]

    return eligible.sort_values(
        [
            "approved_predicted_risk_adjusted_profit_proxy",
            "approval_rate",
        ],
        ascending=[False, False],
    ).iloc[0]


def create_segment_monitoring(df: pd.DataFrame) -> pd.DataFrame:
    logging.info("Creating segment monitoring table...")

    segment_columns = [
        "credit_limit_segment",
        "utilization_segment",
        "repayment_behavior_category",
        "bill_statement_size_segment",
        "payment_amount_segment",
        "age_group",
    ]

    segment_columns = [col for col in segment_columns if col in df.columns]

    rows = []
    portfolio_default_rate = df[TARGET].mean()
    portfolio_avg_pd = df[PREDICTION_COL].mean()

    for col in segment_columns:
        grouped = (
            df.groupby(col, dropna=False)
            .agg(
                customer_count=(TARGET, "size"),
                defaulted_customers=(TARGET, "sum"),
                observed_default_rate=(TARGET, "mean"),
                avg_predicted_default_probability=(PREDICTION_COL, "mean"),
                avg_risk_decile=("predicted_default_risk_decile", "mean"),
                total_balance_exposure_proxy=("balance_exposure_proxy", "sum"),
                total_predicted_expected_loss_proxy=(
                    "predicted_expected_loss_proxy",
                    "sum",
                ),
                total_actual_loss_proxy=("actual_loss_proxy", "sum"),
                total_predicted_risk_adjusted_profit_proxy=(
                    "predicted_risk_adjusted_profit_proxy",
                    "sum",
                ),
            )
            .reset_index()
            .rename(columns={col: "segment_name"})
        )

        grouped["segment_type"] = col
        grouped["portfolio_default_rate"] = portfolio_default_rate
        grouped["portfolio_avg_predicted_pd"] = portfolio_avg_pd
        grouped["default_rate_lift"] = (
            grouped["observed_default_rate"] / portfolio_default_rate
        )
        grouped["prediction_lift"] = (
            grouped["avg_predicted_default_probability"] / portfolio_avg_pd
        )
        grouped["calibration_gap"] = (
            grouped["avg_predicted_default_probability"]
            - grouped["observed_default_rate"]
        )
        grouped["absolute_calibration_gap"] = grouped[
            "calibration_gap"
        ].abs()

        grouped = grouped[grouped["customer_count"] >= MIN_SEGMENT_SIZE]

        rows.append(grouped)

    if not rows:
        return pd.DataFrame()

    segment_df = pd.concat(rows, ignore_index=True)

    segment_df = segment_df[
        [
            "segment_type",
            "segment_name",
            "customer_count",
            "defaulted_customers",
            "observed_default_rate",
            "portfolio_default_rate",
            "default_rate_lift",
            "avg_predicted_default_probability",
            "portfolio_avg_predicted_pd",
            "prediction_lift",
            "calibration_gap",
            "absolute_calibration_gap",
            "avg_risk_decile",
            "total_balance_exposure_proxy",
            "total_predicted_expected_loss_proxy",
            "total_actual_loss_proxy",
            "total_predicted_risk_adjusted_profit_proxy",
        ]
    ]

    numeric_cols = segment_df.select_dtypes(include=[np.number]).columns
    segment_df[numeric_cols] = segment_df[numeric_cols].round(6)

    return segment_df.sort_values(
        [
            "default_rate_lift",
            "total_actual_loss_proxy",
            "absolute_calibration_gap",
        ],
        ascending=[False, False, False],
    )


def create_fairness_monitoring(
    df: pd.DataFrame,
    recommended_threshold: float,
) -> pd.DataFrame:
    logging.info("Creating fairness monitoring table...")

    fairness_columns = [
        "sex_label",
        "education_label",
        "marriage_label",
        "age_group",
    ]

    fairness_columns = [col for col in fairness_columns if col in df.columns]

    rows = []
    portfolio_default_rate = df[TARGET].mean()
    portfolio_flag_rate = (df[PREDICTION_COL] >= recommended_threshold).mean()

    for col in fairness_columns:
        working = df.copy()
        working["flagged_at_recommended_threshold"] = (
            working[PREDICTION_COL] >= recommended_threshold
        ).astype(int)

        grouped = (
            working.groupby(col, dropna=False)
            .agg(
                customer_count=(TARGET, "size"),
                defaulted_customers=(TARGET, "sum"),
                observed_default_rate=(TARGET, "mean"),
                avg_predicted_default_probability=(PREDICTION_COL, "mean"),
                flag_rate_at_recommended_threshold=(
                    "flagged_at_recommended_threshold",
                    "mean",
                ),
                avg_risk_decile=("predicted_default_risk_decile", "mean"),
                total_balance_exposure_proxy=("balance_exposure_proxy", "sum"),
                total_predicted_expected_loss_proxy=(
                    "predicted_expected_loss_proxy",
                    "sum",
                ),
                total_actual_loss_proxy=("actual_loss_proxy", "sum"),
            )
            .reset_index()
            .rename(columns={col: "group_name"})
        )

        grouped["monitoring_dimension"] = col
        grouped["portfolio_default_rate"] = portfolio_default_rate
        grouped["portfolio_flag_rate"] = portfolio_flag_rate
        grouped["default_rate_lift"] = (
            grouped["observed_default_rate"] / portfolio_default_rate
        )
        grouped["flag_rate_difference_vs_portfolio"] = (
            grouped["flag_rate_at_recommended_threshold"] - portfolio_flag_rate
        )
        grouped["calibration_gap"] = (
            grouped["avg_predicted_default_probability"]
            - grouped["observed_default_rate"]
        )

        grouped = grouped[grouped["customer_count"] >= MIN_SEGMENT_SIZE]

        rows.append(grouped)

    if not rows:
        return pd.DataFrame()

    fairness_df = pd.concat(rows, ignore_index=True)

    fairness_df["governance_review_flag"] = np.select(
        [
            fairness_df["flag_rate_difference_vs_portfolio"].abs() >= 0.10,
            fairness_df["calibration_gap"].abs() >= 0.10,
            fairness_df["default_rate_lift"] >= 1.50,
        ],
        [
            "Review flag-rate disparity",
            "Review calibration gap",
            "Review elevated observed risk",
        ],
        default="Standard monitoring",
    )

    fairness_df = fairness_df[
        [
            "monitoring_dimension",
            "group_name",
            "customer_count",
            "defaulted_customers",
            "observed_default_rate",
            "portfolio_default_rate",
            "default_rate_lift",
            "avg_predicted_default_probability",
            "calibration_gap",
            "flag_rate_at_recommended_threshold",
            "portfolio_flag_rate",
            "flag_rate_difference_vs_portfolio",
            "avg_risk_decile",
            "total_balance_exposure_proxy",
            "total_predicted_expected_loss_proxy",
            "total_actual_loss_proxy",
            "governance_review_flag",
        ]
    ]

    numeric_cols = fairness_df.select_dtypes(include=[np.number]).columns
    fairness_df[numeric_cols] = fairness_df[numeric_cols].round(6)

    return fairness_df.sort_values(
        [
            "governance_review_flag",
            "flag_rate_difference_vs_portfolio",
            "default_rate_lift",
        ],
        ascending=[True, False, False],
    )


def create_error_analysis(
    df: pd.DataFrame,
    recommended_threshold: float,
) -> pd.DataFrame:
    logging.info("Creating error analysis table...")

    working = df.copy()

    working["predicted_high_risk_flag"] = (
        working[PREDICTION_COL] >= recommended_threshold
    ).astype(int)

    working["prediction_outcome_type"] = np.select(
        [
            (working[TARGET] == 0) & (working["predicted_high_risk_flag"] == 0),
            (working[TARGET] == 0) & (working["predicted_high_risk_flag"] == 1),
            (working[TARGET] == 1) & (working["predicted_high_risk_flag"] == 0),
            (working[TARGET] == 1) & (working["predicted_high_risk_flag"] == 1),
        ],
        [
            "True negative: non-default approved",
            "False positive: non-default flagged",
            "False negative: default missed",
            "True positive: default flagged",
        ],
        default="Unknown",
    )

    error_summary = (
        working.groupby("prediction_outcome_type")
        .agg(
            customer_count=(TARGET, "size"),
            avg_predicted_default_probability=(PREDICTION_COL, "mean"),
            avg_risk_decile=("predicted_default_risk_decile", "mean"),
            total_balance_exposure_proxy=("balance_exposure_proxy", "sum"),
            total_predicted_expected_loss_proxy=(
                "predicted_expected_loss_proxy",
                "sum",
            ),
            total_actual_loss_proxy=("actual_loss_proxy", "sum"),
            total_predicted_risk_adjusted_profit_proxy=(
                "predicted_risk_adjusted_profit_proxy",
                "sum",
            ),
            total_actual_risk_adjusted_profit_proxy=(
                "actual_risk_adjusted_profit_proxy",
                "sum",
            ),
        )
        .reset_index()
    )

    error_summary["customer_share"] = (
        error_summary["customer_count"] / len(working)
    )

    numeric_cols = error_summary.select_dtypes(include=[np.number]).columns
    error_summary[numeric_cols] = error_summary[numeric_cols].round(6)

    return error_summary.sort_values("prediction_outcome_type")


def create_governance_checklist() -> pd.DataFrame:
    logging.info("Creating governance checklist...")

    checklist_rows = [
        {
            "governance_area": "Data lineage",
            "validation_check": "Model uses processed analysis-ready dataset generated by cleaning script",
            "status": "Completed",
            "evidence_file": str(SCORED_CUSTOMERS_FILE),
        },
        {
            "governance_area": "Target definition",
            "validation_check": "Target is default_payment_next_month from historical dataset",
            "status": "Completed",
            "evidence_file": str(MODEL_METRICS_FILE),
        },
        {
            "governance_area": "Model ranking",
            "validation_check": "Risk decile lift confirms whether model ranks borrower risk effectively",
            "status": "Completed",
            "evidence_file": str(RISK_DECILE_FILE),
        },
        {
            "governance_area": "Calibration",
            "validation_check": "Probability bands compare predicted default probability with observed default rate",
            "status": "Completed",
            "evidence_file": str(CALIBRATION_FILE),
        },
        {
            "governance_area": "Threshold selection",
            "validation_check": "Operating threshold evaluated using approval rate, default capture, and risk-adjusted profitability proxy",
            "status": "Completed",
            "evidence_file": str(THRESHOLD_BUSINESS_FILE),
        },
        {
            "governance_area": "Segment monitoring",
            "validation_check": "Model performance reviewed across utilization, repayment, balance, payment, age, and credit-limit segments",
            "status": "Completed",
            "evidence_file": str(SEGMENT_MONITORING_FILE),
        },
        {
            "governance_area": "Fairness monitoring",
            "validation_check": "Demographic fields reviewed only for monitoring, not direct decision rules",
            "status": "Completed",
            "evidence_file": str(FAIRNESS_MONITORING_FILE),
        },
        {
            "governance_area": "Production limitation",
            "validation_check": "Analysis is documented as a portfolio analytics demonstration rather than a production underwriting system",
            "status": "Documented",
            "evidence_file": str(EXECUTIVE_VALIDATION_SUMMARY_FILE),
        },
    ]

    return pd.DataFrame(checklist_rows)


def create_executive_validation_summary(
    validation_summary_df: pd.DataFrame,
    threshold_business_df: pd.DataFrame,
    recommended_threshold_row: pd.Series,
    risk_decile_df: pd.DataFrame,
    fairness_df: pd.DataFrame,
    segment_df: pd.DataFrame,
) -> None:
    logging.info("Creating executive validation summary...")

    summary = validation_summary_df.iloc[0]
    top_decile = risk_decile_df.sort_values(
        "predicted_default_risk_decile",
        ascending=True,
    ).iloc[0]

    top_segments = segment_df.head(8).copy()
    fairness_flags = fairness_df[
        fairness_df["governance_review_flag"] != "Standard monitoring"
    ].copy()

    lines = [
        "# Executive Validation and Governance Summary",
        "",
        "Project: Credit Risk & Customer Profitability Analytics",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Purpose",
        "",
        "This layer validates the credit-risk model beyond basic accuracy metrics. It tests calibration, risk ranking, threshold tradeoffs, business impact, segment behavior, and fairness-monitoring indicators.",
        "",
        "## Portfolio-Level Validation",
        "",
        f"- Customer records scored: {int(summary['record_count']):,}",
        f"- Portfolio observed default rate: {summary['portfolio_default_rate']:.2%}",
        f"- Average predicted default probability: {summary['avg_predicted_default_probability']:.2%}",
        f"- Calibration gap: {summary['calibration_gap']:.2%}",
        f"- Brier score: {summary['brier_score']:.4f}",
        f"- Top-risk decile default rate: {summary['top_decile_default_rate']:.2%}",
        f"- Bottom-risk decile default rate: {summary['bottom_decile_default_rate']:.2%}",
        f"- Top-risk decile lift vs portfolio: {summary['top_decile_lift_vs_portfolio']:.2f}x",
        "",
        "## Risk Decile Business Impact",
        "",
        f"- Highest-risk decile customer count: {int(top_decile['customer_count']):,}",
        f"- Highest-risk decile observed default rate: {top_decile['observed_default_rate']:.2%}",
        f"- Highest-risk decile default capture rate: {top_decile['default_capture_rate']:.2%}",
        f"- Highest-risk decile actual loss capture rate: {top_decile['actual_loss_capture_rate']:.2%}",
        "",
        "## Recommended Operating Threshold",
        "",
        f"- Recommended threshold: {recommended_threshold_row['threshold']:.3f}",
        f"- Threshold label: {recommended_threshold_row['threshold_policy_label']}",
        f"- Approval rate: {recommended_threshold_row['approval_rate']:.2%}",
        f"- Flag rate: {recommended_threshold_row['flag_rate']:.2%}",
        f"- Approved observed default rate: {recommended_threshold_row['approved_observed_default_rate']:.2%}",
        f"- Historical default capture rate: {recommended_threshold_row['historical_default_capture_rate']:.2%}",
        f"- Approved predicted risk-adjusted profitability proxy: {recommended_threshold_row['approved_predicted_risk_adjusted_profit_proxy']:,.2f}",
        "",
        "## Highest-Risk Segment Monitoring Candidates",
        "",
    ]

    if top_segments.empty:
        lines.append("- No segment rows met the minimum size requirement.")
    else:
        for _, row in top_segments.iterrows():
            lines.append(
                f"- {row['segment_type']} = {row['segment_name']}: "
                f"default rate {row['observed_default_rate']:.2%}, "
                f"default-rate lift {row['default_rate_lift']:.2f}x, "
                f"avg predicted PD {row['avg_predicted_default_probability']:.2%}"
            )

    lines.extend(
        [
            "",
            "## Fairness and Governance Monitoring",
            "",
        ]
    )

    if fairness_flags.empty:
        lines.append(
            "- No fairness-monitoring groups triggered the simple review flags used in this project layer."
        )
    else:
        for _, row in fairness_flags.head(10).iterrows():
            lines.append(
                f"- {row['monitoring_dimension']} = {row['group_name']}: "
                f"{row['governance_review_flag']}; "
                f"flag-rate difference vs portfolio {row['flag_rate_difference_vs_portfolio']:.2%}; "
                f"calibration gap {row['calibration_gap']:.2%}"
            )

    lines.extend(
        [
            "",
            "## Files Created",
            "",
            "- model_validation_summary.csv",
            "- calibration_by_probability_band.csv",
            "- risk_decile_business_summary.csv",
            "- threshold_business_impact.csv",
            "- segment_model_monitoring.csv",
            "- fairness_monitoring_summary.csv",
            "- model_error_analysis.csv",
            "- model_governance_checklist.csv",
            "",
            "## Governance Note",
            "",
            "This project uses demographic fields only for monitoring and fairness review. They should not be framed as direct approval, pricing, or rejection rules. A production model would require stronger validation, regulatory review, adverse action reason codes, bias testing, monitoring over time, and model risk management approval.",
            "",
            "## Analyst Takeaway",
            "",
            "The model is useful not just because it predicts default, but because it ranks customers into actionable risk tiers, identifies where calibration should be monitored, links predicted probability to expected loss and profitability proxies, and supports threshold decisions that balance approval volume against credit risk.",
        ]
    )

    EXECUTIVE_VALIDATION_SUMMARY_FILE.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> None:
    validate_inputs()

    print("=" * 80)
    print("Running model validation and governance layer...")
    print("=" * 80)

    df = load_scored_customers()

    validation_summary_df = create_validation_summary(df)
    calibration_df = create_calibration_table(df)
    risk_decile_df = create_risk_decile_business_summary(df)
    threshold_business_df = create_threshold_business_impact(df)
    recommended_threshold_row = choose_recommended_threshold(
        threshold_business_df
    )

    segment_df = create_segment_monitoring(df)
    # These fields are used only for monitoring and fairness review,
    # not as direct production approval or rejection rules.
    fairness_df = create_fairness_monitoring(
        df,
        recommended_threshold=float(recommended_threshold_row["threshold"]),
    )
    error_analysis_df = create_error_analysis(
        df,
        recommended_threshold=float(recommended_threshold_row["threshold"]),
    )
    governance_checklist_df = create_governance_checklist()

    validation_summary_df.to_csv(VALIDATION_SUMMARY_FILE, index=False)
    calibration_df.to_csv(CALIBRATION_FILE, index=False)
    risk_decile_df.to_csv(RISK_DECILE_FILE, index=False)
    threshold_business_df.to_csv(THRESHOLD_BUSINESS_FILE, index=False)
    segment_df.to_csv(SEGMENT_MONITORING_FILE, index=False)
    fairness_df.to_csv(FAIRNESS_MONITORING_FILE, index=False)
    error_analysis_df.to_csv(ERROR_ANALYSIS_FILE, index=False)
    governance_checklist_df.to_csv(GOVERNANCE_CHECKLIST_FILE, index=False)

    create_executive_validation_summary(
        validation_summary_df=validation_summary_df,
        threshold_business_df=threshold_business_df,
        recommended_threshold_row=recommended_threshold_row,
        risk_decile_df=risk_decile_df,
        fairness_df=fairness_df,
        segment_df=segment_df,
    )

    validation_payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "recommended_threshold": float(recommended_threshold_row["threshold"]),
        "recommended_threshold_label": str(
            recommended_threshold_row["threshold_policy_label"]
        ),
        "portfolio_default_rate": float(
            validation_summary_df.iloc[0]["portfolio_default_rate"]
        ),
        "avg_predicted_default_probability": float(
            validation_summary_df.iloc[0][
                "avg_predicted_default_probability"
            ]
        ),
        "calibration_gap": float(
            validation_summary_df.iloc[0]["calibration_gap"]
        ),
        "brier_score": float(validation_summary_df.iloc[0]["brier_score"]),
        "top_decile_lift_vs_portfolio": float(
            validation_summary_df.iloc[0]["top_decile_lift_vs_portfolio"]
        ),
        "output_files": {
            "validation_summary": str(VALIDATION_SUMMARY_FILE),
            "calibration": str(CALIBRATION_FILE),
            "risk_decile": str(RISK_DECILE_FILE),
            "threshold_business": str(THRESHOLD_BUSINESS_FILE),
            "segment_monitoring": str(SEGMENT_MONITORING_FILE),
            "fairness_monitoring": str(FAIRNESS_MONITORING_FILE),
            "error_analysis": str(ERROR_ANALYSIS_FILE),
            "governance_checklist": str(GOVERNANCE_CHECKLIST_FILE),
            "executive_summary": str(EXECUTIVE_VALIDATION_SUMMARY_FILE),
        },
    }

    (OUTPUT_DIR / "validation_metadata.json").write_text(
        json.dumps(validation_payload, indent=2),
        encoding="utf-8",
    )

    print("=" * 80)
    print("Model validation and governance completed successfully.")
    print("=" * 80)

    print(f"\nValidation outputs saved to:\n{OUTPUT_DIR}")

    print("\nValidation summary:")
    print(validation_summary_df.T)

    print("\nRecommended threshold:")
    print(recommended_threshold_row)

    print("\nRisk decile business summary:")
    print(risk_decile_df)

    print("\nTop segment monitoring rows:")
    print(segment_df.head(10))

    print("\nFairness monitoring preview:")
    print(fairness_df.head(10))

    print(f"\nExecutive validation summary saved to:\n{EXECUTIVE_VALIDATION_SUMMARY_FILE}")


if __name__ == "__main__":
    main()