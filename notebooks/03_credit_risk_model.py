"""
03_credit_risk_model.py
Modeling layer for the Credit Risk & Customer Profitability Analytics project.
This script trains supervised default-risk models using the cleaned customer-level
dataset from 00_clean_raw_data.py. The goal is to move from historical segment-level
default patterns to borrower-level predicted probability of default.
I compare a simple linear benchmark, a random forest, and a histogram gradient
boosting model, then evaluate the best model through ROC-AUC, PR-AUC, precision,
recall, threshold tradeoffs, lift by decile, and feature importance. The final
scored customer file is used for Tableau reporting and portfolio strategy analysis.
This is a portfolio analytics model, not a production underwriting system.
"""

from pathlib import Path
from datetime import datetime
import json
import logging
import joblib

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE / "data" / "processed" / "credit_card_default_analysis_ready.csv"
OUTPUT_DIR = BASE / "data" / "processed" / "model_outputs"
MODEL_DIR = BASE / "models"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_METRICS_FILE = OUTPUT_DIR / "model_metrics.json"
MODEL_COMPARISON_FILE = OUTPUT_DIR / "model_comparison.csv"
THRESHOLD_ANALYSIS_FILE = OUTPUT_DIR / "threshold_analysis.csv"
LIFT_BY_DECILE_FILE = OUTPUT_DIR / "lift_by_decile.csv"
FEATURE_IMPORTANCE_FILE = OUTPUT_DIR / "feature_importance.csv"
SCORED_CUSTOMERS_FILE = OUTPUT_DIR / "credit_risk_scored_customers.csv"
EXECUTIVE_MODEL_SUMMARY_FILE = OUTPUT_DIR / "_executive_model_summary.md"
TRAINED_MODEL_FILE = MODEL_DIR / "credit_default_probability_model.joblib"

TARGET = "default_payment_next_month"
ID_COL = "customer_id"

LGD_ASSUMPTION = 0.60
SIX_MONTH_REVENUE_RATE_PROXY = 0.09
RANDOM_STATE = 42
TEST_SIZE = 0.20

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def validate_input_file() -> None:
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Missing input file: {INPUT_FILE}\n"
            "Run notebooks/00_clean_raw_data.py first."
        )


def load_analysis_ready_data() -> pd.DataFrame:
    logging.info("Loading analysis-ready modeling data...")
    df = pd.read_csv(INPUT_FILE)

    if TARGET not in df.columns:
        raise ValueError(f"Missing target column: {TARGET}")

    if ID_COL not in df.columns:
        raise ValueError(f"Missing customer ID column: {ID_COL}")

    return df


def get_feature_columns(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    numeric_features = [
        "credit_limit",
        "age",
        "repay_status_sep",
        "repay_status_aug",
        "repay_status_jul",
        "repay_status_jun",
        "repay_status_may",
        "repay_status_apr",
        "bill_amt_sep",
        "bill_amt_aug",
        "bill_amt_jul",
        "bill_amt_jun",
        "bill_amt_may",
        "bill_amt_apr",
        "pay_amt_sep",
        "pay_amt_aug",
        "pay_amt_jul",
        "pay_amt_jun",
        "pay_amt_may",
        "pay_amt_apr",
        "max_repayment_delay",
        "avg_repayment_status",
        "months_with_payment_delay",
        "months_with_serious_delay",
        "any_payment_delay_flag",
        "serious_payment_delay_flag",
        "avg_bill_amount",
        "avg_payment_amount",
        "utilization_proxy",
        "recent_payment_to_bill_ratio",
    ]

    #Keep demographic lables in the feature set for analysis, but this project is not 
    #using the model as productionapproval or rejecton systems.
    categorical_features = [
        "sex_label",
        "education_label",
        "marriage_label",
        "age_group",
        "credit_limit_segment",
        "utilization_segment",
        "repayment_behavior_category",
        "bill_statement_size_segment",
        "payment_amount_segment",
        "portfolio_monitoring_flag",
    ]

    numeric_features = [col for col in numeric_features if col in df.columns]
    categorical_features = [col for col in categorical_features if col in df.columns]

    return numeric_features, categorical_features


def build_preprocessor(
    numeric_features: list[str],
    categorical_features: list[str],
    scale_numeric: bool,
) -> ColumnTransformer:
    if scale_numeric:
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", StandardScaler()),
            ]
        )
    else:
        numeric_pipeline = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
            ]
        )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    return ColumnTransformer(
        transformers=[
            ("num", numeric_pipeline, numeric_features),
            ("cat", categorical_pipeline, categorical_features),
        ],
        remainder="drop",
    )


def build_candidate_models(
    numeric_features: list[str],
    categorical_features: list[str],
) -> dict[str, Pipeline]:
    return {
        "logistic_regression_balanced": Pipeline(
            steps=[
                (
                    "preprocess",
                    build_preprocessor(
                        numeric_features=numeric_features,
                        categorical_features=categorical_features,
                        scale_numeric=True,
                    ),
                ),
                (
                    "classifier",
                    LogisticRegression(
                        max_iter=3000,
                        class_weight="balanced",
                        solver="lbfgs",
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
        "random_forest_balanced": Pipeline(
            steps=[
                (
                    "preprocess",
                    build_preprocessor(
                        numeric_features=numeric_features,
                        categorical_features=categorical_features,
                        scale_numeric=False,
                    ),
                ),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=350,
                        max_depth=10,
                        min_samples_leaf=40,
                        class_weight="balanced_subsample",
                        random_state=RANDOM_STATE,
                        n_jobs=-1,
                    ),
                ),
            ]
        ),
        "hist_gradient_boosting": Pipeline(
            steps=[
                (
                    "preprocess",
                    build_preprocessor(
                        numeric_features=numeric_features,
                        categorical_features=categorical_features,
                        scale_numeric=False,
                    ),
                ),
                (
                    "classifier",
                    HistGradientBoostingClassifier(
                        learning_rate=0.06,
                        max_iter=250,
                        max_leaf_nodes=31,
                        l2_regularization=0.10,
                        random_state=RANDOM_STATE,
                    ),
                ),
            ]
        ),
    }


def calculate_metrics(
    model_name: str,
    y_true: pd.Series,
    y_probability: np.ndarray,
    threshold: float = 0.50,
) -> dict:
    y_pred = (y_probability >= threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    return {
        "model_name": model_name,
        "threshold": threshold,
        "roc_auc": float(roc_auc_score(y_true, y_probability)),
        "pr_auc": float(average_precision_score(y_true, y_probability)),
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
    }


def create_threshold_analysis(
    y_true: pd.Series,
    y_probability: np.ndarray,
) -> pd.DataFrame:
    rows = []

    for threshold in np.arange(0.10, 0.81, 0.05):
        y_pred = (y_probability >= threshold).astype(int)
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

        approval_rate = float(np.mean(y_pred == 0))
        review_or_decline_rate = float(np.mean(y_pred == 1))

        rows.append(
            {
                "threshold": round(float(threshold), 2),
                "accuracy": accuracy_score(y_true, y_pred),
                "recall": recall_score(y_true, y_pred, zero_division=0),
                "precision": precision_score(y_true, y_pred, zero_division=0),
                "true_negatives": tn,
                "false_positives": fp,
                "false_negatives": fn,
                "true_positives": tp,
                "approval_rate_if_low_risk_approved": approval_rate,
                "review_or_decline_rate_if_high_risk_flagged": review_or_decline_rate,
            }
        )

    threshold_df = pd.DataFrame(rows)

    numeric_cols = threshold_df.select_dtypes(include=[np.number]).columns
    threshold_df[numeric_cols] = threshold_df[numeric_cols].round(4)

    return threshold_df


def create_lift_by_decile(
    y_true: pd.Series,
    y_probability: np.ndarray,
) -> pd.DataFrame:
    lift_df = pd.DataFrame(
        {
            "actual_default": y_true.to_numpy(),
            "predicted_default_probability": y_probability,
        }
    )
    #Risk decile make the model easier to evaluate as a borrower-ranking tool.
    #This is more usefull for portfolio review than accuracy bu itself.
    lift_df["risk_decile"] = pd.qcut(
        lift_df["predicted_default_probability"].rank(method="first"),
        q=10,
        labels=False,
    )

    lift_df["risk_decile"] = 10 - lift_df["risk_decile"]

    portfolio_default_rate = lift_df["actual_default"].mean()

    decile_summary = (
        lift_df.groupby("risk_decile", as_index=False)
        .agg(
            customer_count=("actual_default", "size"),
            defaulted_customers=("actual_default", "sum"),
            observed_default_rate=("actual_default", "mean"),
            avg_predicted_default_probability=(
                "predicted_default_probability",
                "mean",
            ),
            min_predicted_default_probability=(
                "predicted_default_probability",
                "min",
            ),
            max_predicted_default_probability=(
                "predicted_default_probability",
                "max",
            ),
        )
        .sort_values("risk_decile", ascending=True)
    )

    decile_summary["portfolio_default_rate"] = portfolio_default_rate
    decile_summary["lift_vs_portfolio"] = (
        decile_summary["observed_default_rate"]
        / portfolio_default_rate
    )

    numeric_cols = decile_summary.select_dtypes(include=[np.number]).columns
    decile_summary[numeric_cols] = decile_summary[numeric_cols].round(4)

    return decile_summary


def get_feature_names(model: Pipeline) -> list[str]:
    preprocessor = model.named_steps["preprocess"]
    feature_names = preprocessor.get_feature_names_out()
    return [str(name).replace("num__", "").replace("cat__", "") for name in feature_names]


def create_feature_importance(
    model: Pipeline,
    model_name: str,
    X_validation: pd.DataFrame,
    y_validation: pd.Series,
) -> pd.DataFrame:
    logging.info("Calculating permutation feature importance...")

    permutation_result = permutation_importance(
        model,
        X_validation,
        y_validation,
        scoring="roc_auc",
        n_repeats=5,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    importance_df = pd.DataFrame(
        {
            "model_name": model_name,
            "feature_name": X_validation.columns,
            "importance_value": permutation_result.importances_mean,
            "importance_std": permutation_result.importances_std,
            "importance_type": "permutation_importance_roc_auc",
        }
    )

    importance_df = (
        importance_df.sort_values("importance_value", ascending=False)
        .reset_index(drop=True)
    )

    importance_df["importance_rank"] = importance_df.index + 1

    return importance_df

def score_full_portfolio(
    df: pd.DataFrame,
    model: Pipeline,
    feature_cols: list[str],
) -> pd.DataFrame:
    scored = df.copy()

    scored["predicted_default_probability"] = model.predict_proba(
        scored[feature_cols]
    )[:, 1]

    scored["predicted_default_risk_decile"] = pd.qcut(
        scored["predicted_default_probability"].rank(method="first"),
        q=10,
        labels=False,
    )

    scored["predicted_default_risk_decile"] = (
        10 - scored["predicted_default_risk_decile"]
    )

    scored["credit_line_exposure"] = scored["credit_limit"].clip(lower=0)

    if "avg_bill_amount" in scored.columns:
        scored["balance_exposure_proxy"] = scored["avg_bill_amount"].clip(lower=0)
    else:
        scored["balance_exposure_proxy"] = scored["bill_amt_sep"].clip(lower=0)

    scored["lgd_assumption"] = LGD_ASSUMPTION
    scored["six_month_revenue_rate_proxy"] = SIX_MONTH_REVENUE_RATE_PROXY

    scored["predicted_expected_loss_proxy"] = (
        scored["predicted_default_probability"]
        * scored["balance_exposure_proxy"]
        * scored["lgd_assumption"]
    )

    scored["predicted_revenue_proxy_6mo"] = (
        scored["balance_exposure_proxy"]
        * scored["six_month_revenue_rate_proxy"]
    )

    scored["predicted_risk_adjusted_profit_proxy"] = (
        scored["predicted_revenue_proxy_6mo"]
        - scored["predicted_expected_loss_proxy"]
    )

    risk_cutoff = scored["predicted_default_probability"].median()
    profit_cutoff = scored["predicted_risk_adjusted_profit_proxy"].median()

    scored["model_risk_profit_segment"] = np.select(
        [
            (
                scored["predicted_default_probability"] < risk_cutoff
            )
            & (
                scored["predicted_risk_adjusted_profit_proxy"] >= profit_cutoff
            ),
            (
                scored["predicted_default_probability"] < risk_cutoff
            )
            & (
                scored["predicted_risk_adjusted_profit_proxy"] < profit_cutoff
            ),
            (
                scored["predicted_default_probability"] >= risk_cutoff
            )
            & (
                scored["predicted_risk_adjusted_profit_proxy"] >= profit_cutoff
            ),
            (
                scored["predicted_default_probability"] >= risk_cutoff
            )
            & (
                scored["predicted_risk_adjusted_profit_proxy"] < profit_cutoff
            ),
        ],
        [
            "Low-risk / high-profit",
            "Low-risk / low-profit",
            "High-risk / high-profit",
            "High-risk / low-profit",
        ],
        default="Unclassified",
    )

    scored["model_credit_strategy"] = np.select(
        [
            scored["predicted_default_risk_decile"].isin([1, 2]),
            scored["predicted_default_risk_decile"].isin([3, 4]),
            scored["predicted_default_risk_decile"].isin([5, 6, 7]),
            scored["predicted_default_risk_decile"].isin([8, 9, 10]),
        ],
        [
            "Manual review / tighter controls",
            "Monitor or price for risk",
            "Standard approval policy",
            "Growth / retention candidate",
        ],
        default="Standard monitoring",
    )

    return scored


def create_executive_model_summary(
    best_model_name: str,
    best_metrics: dict,
    lift_df: pd.DataFrame,
    threshold_df: pd.DataFrame,
    feature_importance_df: pd.DataFrame,
    train_size: int,
    test_size: int,
) -> None:
    top_decile = lift_df.sort_values("risk_decile", ascending=True).iloc[0]
    top_features = feature_importance_df.head(10)

    lines = [
        "# Executive Model Summary",
        "",
        "Project: Credit Risk & Customer Profitability Analytics",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Purpose",
        "",
        "This Python modeling layer estimates borrower-level probability of default and converts model scores into expected loss, revenue proxy, and risk-adjusted profitability proxy outputs.",
        "",
        "## Dataset Split",
        "",
        f"- Training records: {train_size:,}",
        f"- Test records: {test_size:,}",
        f"- Test size: {TEST_SIZE:.0%}",
        f"- Stratified split: Yes",
        "",
        "## Best Model",
        "",
        f"- Selected model: {best_model_name}",
        f"- ROC-AUC: {best_metrics['roc_auc']:.4f}",
        f"- PR-AUC: {best_metrics['pr_auc']:.4f}",
        f"- Accuracy at 0.50 threshold: {best_metrics['accuracy']:.4f}",
        f"- Recall at 0.50 threshold: {best_metrics['recall']:.4f}",
        f"- Precision at 0.50 threshold: {best_metrics['precision']:.4f}",
        "",
        "## Lift Analysis",
        "",
        f"- Highest-risk decile observed default rate: {top_decile['observed_default_rate']:.2%}",
        f"- Portfolio test default rate: {top_decile['portfolio_default_rate']:.2%}",
        f"- Highest-risk decile lift vs portfolio: {top_decile['lift_vs_portfolio']:.2f}x",
        "",
        "## Top Model Drivers",
        "",
    ]

    if not top_features.empty:
        for _, row in top_features.iterrows():
            lines.append(
                f"- {int(row['importance_rank'])}. {row['feature_name']}: "
                f"{row['importance_value']:.6f}"
            )
    else:
        lines.append("- Feature importance was not available for this model type.")

    lines.extend(
        [
            "",
            "## Files Created",
            "",
            "- model_comparison.csv",
            "- model_metrics.json",
            "- threshold_analysis.csv",
            "- lift_by_decile.csv",
            "- feature_importance.csv",
            "- credit_risk_scored_customers.csv",
            "- credit_default_probability_model.joblib",
            "",
            "## Governance Note",
            "",
            "This model is for portfolio analytics and project demonstration. Demographic fields should be handled carefully and reviewed for fairness before any production credit decisioning use.",
            "",
            "## Next Step",
            "",
            "Use the scored customer output in Tableau to visualize predicted probability of default, expected loss proxy, risk-adjusted profitability proxy, risk deciles, and recommended portfolio strategy.",
        ]
    )

    EXECUTIVE_MODEL_SUMMARY_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    validate_input_file()

    df = load_analysis_ready_data()

    numeric_features, categorical_features = get_feature_columns(df)
    feature_cols = numeric_features + categorical_features

    model_df = df[[ID_COL, TARGET] + feature_cols].copy()
    X = model_df[feature_cols]
    y = model_df[TARGET].astype(int)

    X_train, X_test, y_train, y_test, id_train, id_test = train_test_split(
        X,
        y,
        model_df[ID_COL],
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    logging.info("Training candidate models...")

    candidate_models = build_candidate_models(
        numeric_features=numeric_features,
        categorical_features=categorical_features,
    )

    comparison_rows = []
    trained_models = {}

    for model_name, model in candidate_models.items():
        logging.info("Training model: %s", model_name)

        model.fit(X_train, y_train)

        y_probability = model.predict_proba(X_test)[:, 1]
        metrics = calculate_metrics(
            model_name=model_name,
            y_true=y_test,
            y_probability=y_probability,
            threshold=0.50,
        )

        comparison_rows.append(metrics)
        trained_models[model_name] = model

    comparison_df = pd.DataFrame(comparison_rows).sort_values(
        ["roc_auc", "pr_auc"],
        ascending=[False, False],
    )

    best_model_name = comparison_df.iloc[0]["model_name"]
    best_model = trained_models[best_model_name]

    best_probability = best_model.predict_proba(X_test)[:, 1]
    best_metrics = calculate_metrics(
        model_name=best_model_name,
        y_true=y_test,
        y_probability=best_probability,
        threshold=0.50,
    )

    threshold_df = create_threshold_analysis(
        y_true=y_test,
        y_probability=best_probability,
    )

    lift_df = create_lift_by_decile(
        y_true=y_test,
        y_probability=best_probability,
    )

    feature_importance_df = create_feature_importance(
        model=best_model,
        model_name=best_model_name,
        X_validation=X_test,
        y_validation=y_test,
    )

    scored_customers_df = score_full_portfolio(
        df=df,
        model=best_model,
        feature_cols=feature_cols,
    )

    metrics_payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_file": str(INPUT_FILE),
        "best_model_name": best_model_name,
        "train_records": int(len(X_train)),
        "test_records": int(len(X_test)),
        "target_default_rate_overall": float(y.mean()),
        "target_default_rate_train": float(y_train.mean()),
        "target_default_rate_test": float(y_test.mean()),
        "best_model_metrics": best_metrics,
        "candidate_model_metrics": comparison_rows,
        "confusion_matrix_labels": {
            "true_negatives": "Actual non-default predicted non-default",
            "false_positives": "Actual non-default predicted default",
            "false_negatives": "Actual default predicted non-default",
            "true_positives": "Actual default predicted default",
        },
    }

    MODEL_METRICS_FILE.write_text(
        json.dumps(metrics_payload, indent=2),
        encoding="utf-8",
    )

    comparison_df.to_csv(MODEL_COMPARISON_FILE, index=False)
    threshold_df.to_csv(THRESHOLD_ANALYSIS_FILE, index=False)
    lift_df.to_csv(LIFT_BY_DECILE_FILE, index=False)
    feature_importance_df.to_csv(FEATURE_IMPORTANCE_FILE, index=False)
    scored_customers_df.to_csv(SCORED_CUSTOMERS_FILE, index=False)

    joblib.dump(best_model, TRAINED_MODEL_FILE)

    create_executive_model_summary(
        best_model_name=best_model_name,
        best_metrics=best_metrics,
        lift_df=lift_df,
        threshold_df=threshold_df,
        feature_importance_df=feature_importance_df,
        train_size=len(X_train),
        test_size=len(X_test),
    )

    print("=" * 80)
    print("Credit risk model completed successfully.")
    print("=" * 80)
    print(f"\nBest model: {best_model_name}")
    print("\nBest model metrics:")
    print(json.dumps(best_metrics, indent=2))

    print("\nModel comparison:")
    print(comparison_df)

    print("\nLift by decile:")
    print(lift_df)

    print("\nTop feature importance:")
    print(feature_importance_df.head(20))

    print(f"\nModel outputs saved to:\n{OUTPUT_DIR}")
    print(f"\nTrained model saved to:\n{TRAINED_MODEL_FILE}")


if __name__ == "__main__":
    main()
