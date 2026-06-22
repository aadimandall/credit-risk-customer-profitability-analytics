"""
01_sql_portfolio_analysis.py
SQL portfolio analysis layer for the Credit Risk & Customer Profitability Analytics project.
This script uses the cleaned customer-level dataset from 00_clean_raw_data.py and builds
the portfolio analysis layer before any machine learning is introduced. I use DuckDB here
because the questions are naturally SQL-style portfolio questions: default rate, exposure,
utilization, expected loss proxy, revenue proxy, risk-adjusted profitability, and segment
risk concentration.
The outputs from this script are used later for policy simulation, modeling context, and
Tableau reporting. The profitability fields are proxy assumptions because the public dataset
does not include real APR, recoveries, charge-offs, or account-level profit.
"""

from pathlib import Path
from datetime import datetime
import logging

import duckdb
import pandas as pd

BASE = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE / "data" / "processed" / "credit_card_default_analysis_ready.csv"
OUTPUT_DIR = BASE / "data" / "processed" / "sql_outputs"
SQL_DIR = BASE / "sql"

SQL_LOG_FILE = SQL_DIR / "executed_portfolio_analysis_queries.sql"
EXECUTIVE_SUMMARY_FILE = OUTPUT_DIR / "_executive_sql_summary.md"
TABLEAU_SEGMENT_FILE = OUTPUT_DIR / "tableau_segment_risk_profitability.csv"
TABLEAU_CUSTOMER_FILE = OUTPUT_DIR / "tableau_customer_portfolio_base.csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SQL_DIR.mkdir(parents=True, exist_ok=True)

# Public dataset limitation:
# The UCI dataset does not include APR, interest income, fees, recoveries,
# charge-off amount, or true account-level profit. I use these assumptions
# only as transparent proxies for portfolio strategy analysis.
LGD_ASSUMPTION = 0.60
SIX_MONTH_REVENUE_RATE_PROXY = 0.09
MIN_SEGMENT_SIZE = 100

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


def create_portfolio_view(con: duckdb.DuckDBPyConnection) -> None:
    logging.info("Loading analysis-ready dataset into DuckDB...")

    con.execute(
        """
        CREATE OR REPLACE TABLE credit_card_portfolio AS
        SELECT *
        FROM read_csv_auto(?)
        """,
        [str(INPUT_FILE)],
    )

    logging.info("Creating enriched portfolio view...")
    #This view keeps the raw customer fields and adds the porfolio economics
    #used throuhgout the SQL layer. The loss and revenue fields are proxies,
    #not real bank profitability.
    con.execute(
        f"""
        CREATE OR REPLACE VIEW portfolio_enriched AS
        SELECT
            *,

            GREATEST(CAST(credit_limit AS DOUBLE), 0) AS credit_line_exposure,
            GREATEST(CAST(bill_amt_sep AS DOUBLE), 0) AS current_balance_exposure,
            GREATEST(CAST(avg_bill_amount AS DOUBLE), 0) AS avg_balance_exposure,

            CASE
                WHEN credit_limit > 0
                    THEN GREATEST(CAST(bill_amt_sep AS DOUBLE), 0) / credit_limit
                ELSE NULL
            END AS utilization_clean,

            GREATEST(CAST(avg_bill_amount AS DOUBLE), 0)
                * {SIX_MONTH_REVENUE_RATE_PROXY} AS revenue_proxy_6mo,

            CAST(default_payment_next_month AS DOUBLE)
                * GREATEST(CAST(avg_bill_amount AS DOUBLE), 0)
                * {LGD_ASSUMPTION} AS realized_loss_proxy,

            (
                GREATEST(CAST(avg_bill_amount AS DOUBLE), 0)
                * {SIX_MONTH_REVENUE_RATE_PROXY}
            )
            -
            (
                CAST(default_payment_next_month AS DOUBLE)
                * GREATEST(CAST(avg_bill_amount AS DOUBLE), 0)
                * {LGD_ASSUMPTION}
            ) AS observed_risk_adjusted_profit_proxy,

            CASE
                WHEN serious_payment_delay_flag = 1 THEN 'High approval risk'
                WHEN any_payment_delay_flag = 1 THEN 'Moderate approval risk'
                WHEN utilization_proxy >= 0.90 THEN 'Utilization watchlist'
                ELSE 'Lower approval risk'
            END AS approval_risk_band,

            CASE
                WHEN serious_payment_delay_flag = 1 THEN 'Serious delinquency history'
                WHEN utilization_proxy >= 0.90 THEN 'High utilization'
                WHEN recent_payment_to_bill_ratio < 0.10 THEN 'Weak recent repayment'
                WHEN months_with_payment_delay >= 2 THEN 'Repeated payment delays'
                WHEN avg_payment_amount <= 0 THEN 'No meaningful payment activity'
                ELSE 'Lower observed risk indicators'
            END AS primary_risk_reason

        FROM credit_card_portfolio;
        """
    )


def segment_risk_return_query(segment_column: str, segment_label: str) -> str:
    return f"""
        WITH benchmark AS (
            SELECT
                COUNT(*) AS portfolio_customers,
                AVG(default_payment_next_month) AS portfolio_default_rate,
                SUM(current_balance_exposure) AS portfolio_current_balance_exposure,
                AVG(observed_risk_adjusted_profit_proxy) AS portfolio_avg_rap
            FROM portfolio_enriched
        ),

        segment_base AS (
            SELECT
                '{segment_label}' AS segmentation_type,
                COALESCE(CAST({segment_column} AS VARCHAR), 'Unknown') AS segment_name,

                COUNT(*) AS customer_count,
                SUM(default_payment_next_month) AS defaulted_customers,
                AVG(default_payment_next_month) AS observed_default_rate,

                SUM(credit_line_exposure) AS total_credit_line_exposure,
                SUM(current_balance_exposure) AS total_current_balance_exposure,
                AVG(current_balance_exposure) AS avg_current_balance_exposure,
                AVG(avg_balance_exposure) AS avg_balance_exposure,

                AVG(utilization_clean) AS avg_utilization,
                AVG(avg_payment_amount) AS avg_payment_amount,
                AVG(recent_payment_to_bill_ratio) AS avg_recent_payment_to_bill_ratio,
                AVG(months_with_payment_delay) AS avg_months_with_payment_delay,
                AVG(months_with_serious_delay) AS avg_months_with_serious_delay,

                SUM(revenue_proxy_6mo) AS total_revenue_proxy_6mo,
                SUM(realized_loss_proxy) AS total_realized_loss_proxy,
                SUM(observed_risk_adjusted_profit_proxy) AS total_observed_rap_proxy,
                AVG(observed_risk_adjusted_profit_proxy) AS avg_observed_rap_proxy

            FROM portfolio_enriched
            GROUP BY {segment_column}
            HAVING COUNT(*) >= {MIN_SEGMENT_SIZE}
        ),

        scored AS (
            SELECT
                s.*,
                b.portfolio_default_rate,
                b.portfolio_current_balance_exposure,
                b.portfolio_avg_rap,

                s.observed_default_rate / NULLIF(b.portfolio_default_rate, 0)
                    AS default_rate_lift,

                s.total_current_balance_exposure
                    / NULLIF(b.portfolio_current_balance_exposure, 0)
                    AS exposure_share,

                s.observed_default_rate
                    * s.avg_balance_exposure
                    * {LGD_ASSUMPTION} AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * {SIX_MONTH_REVENUE_RATE_PROXY} AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * {SIX_MONTH_REVENUE_RATE_PROXY}
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * {LGD_ASSUMPTION}
                ) AS avg_risk_adjusted_profit_proxy

            FROM segment_base s
            CROSS JOIN benchmark b
        ),

        classified AS (
            SELECT
                *,

                CASE
                    WHEN observed_default_rate <= portfolio_default_rate
                     AND avg_risk_adjusted_profit_proxy >= portfolio_avg_rap
                        THEN 'Low-risk / high-profit'

                    WHEN observed_default_rate <= portfolio_default_rate
                     AND avg_risk_adjusted_profit_proxy < portfolio_avg_rap
                        THEN 'Low-risk / low-profit'

                    WHEN observed_default_rate > portfolio_default_rate
                     AND avg_risk_adjusted_profit_proxy >= portfolio_avg_rap
                        THEN 'High-risk / high-profit'

                    ELSE 'High-risk / low-profit'
                END AS risk_profit_segment

            FROM scored
        )

        SELECT
            segmentation_type,
            segment_name,

            customer_count,
            defaulted_customers,

            ROUND(observed_default_rate, 4) AS observed_default_rate,
            ROUND(portfolio_default_rate, 4) AS portfolio_default_rate,
            ROUND(default_rate_lift, 2) AS default_rate_lift,

            ROUND(total_credit_line_exposure, 2) AS total_credit_line_exposure,
            ROUND(total_current_balance_exposure, 2) AS total_current_balance_exposure,
            ROUND(exposure_share, 4) AS exposure_share,

            ROUND(avg_current_balance_exposure, 2) AS avg_current_balance_exposure,
            ROUND(avg_balance_exposure, 2) AS avg_balance_exposure,

            ROUND(avg_utilization, 4) AS avg_utilization,
            ROUND(avg_payment_amount, 2) AS avg_payment_amount,
            ROUND(avg_recent_payment_to_bill_ratio, 4) AS avg_recent_payment_to_bill_ratio,

            ROUND(avg_months_with_payment_delay, 2) AS avg_months_with_payment_delay,
            ROUND(avg_months_with_serious_delay, 2) AS avg_months_with_serious_delay,

            ROUND(total_revenue_proxy_6mo, 2) AS total_revenue_proxy_6mo,
            ROUND(total_realized_loss_proxy, 2) AS total_realized_loss_proxy,
            ROUND(total_observed_rap_proxy, 2) AS total_observed_risk_adjusted_profit_proxy,

            ROUND(avg_revenue_proxy_6mo, 2) AS avg_revenue_proxy_6mo,
            ROUND(avg_expected_loss_proxy, 2) AS avg_expected_loss_proxy,
            ROUND(avg_risk_adjusted_profit_proxy, 2) AS avg_risk_adjusted_profit_proxy,

            risk_profit_segment,

            CASE
                WHEN risk_profit_segment = 'Low-risk / high-profit'
                    THEN 'Prioritize growth, retention, and cross-sell'

                WHEN risk_profit_segment = 'Low-risk / low-profit'
                    THEN 'Maintain efficiently; do not over-invest acquisition spend'

                WHEN risk_profit_segment = 'High-risk / high-profit'
                    THEN 'Monitor, reprice, limit line increases, or add controls'

                ELSE 'Restrict, reduce exposure, or require stronger repayment behavior'
            END AS recommended_action

        FROM classified
        ORDER BY
            avg_expected_loss_proxy DESC,
            observed_default_rate DESC,
            total_current_balance_exposure DESC;
    """


def repayment_history_query() -> str:
    return """
        WITH monthly AS (
            SELECT customer_id, default_payment_next_month, 1 AS month_order, 'April' AS statement_month,
                   repay_status_apr AS repayment_status, bill_amt_apr AS bill_amount, pay_amt_apr AS payment_amount
            FROM portfolio_enriched
            UNION ALL
            SELECT customer_id, default_payment_next_month, 2 AS month_order, 'May' AS statement_month,
                   repay_status_may AS repayment_status, bill_amt_may AS bill_amount, pay_amt_may AS payment_amount
            FROM portfolio_enriched
            UNION ALL
            SELECT customer_id, default_payment_next_month, 3 AS month_order, 'June' AS statement_month,
                   repay_status_jun AS repayment_status, bill_amt_jun AS bill_amount, pay_amt_jun AS payment_amount
            FROM portfolio_enriched
            UNION ALL
            SELECT customer_id, default_payment_next_month, 4 AS month_order, 'July' AS statement_month,
                   repay_status_jul AS repayment_status, bill_amt_jul AS bill_amount, pay_amt_jul AS payment_amount
            FROM portfolio_enriched
            UNION ALL
            SELECT customer_id, default_payment_next_month, 5 AS month_order, 'August' AS statement_month,
                   repay_status_aug AS repayment_status, bill_amt_aug AS bill_amount, pay_amt_aug AS payment_amount
            FROM portfolio_enriched
            UNION ALL
            SELECT customer_id, default_payment_next_month, 6 AS month_order, 'September' AS statement_month,
                   repay_status_sep AS repayment_status, bill_amt_sep AS bill_amount, pay_amt_sep AS payment_amount
            FROM portfolio_enriched
        )

        SELECT
            month_order,
            statement_month,
            COUNT(*) AS customer_months,
            ROUND(AVG(default_payment_next_month), 4) AS default_rate,
            ROUND(AVG(repayment_status), 4) AS avg_repayment_status,
            ROUND(AVG(CASE WHEN repayment_status >= 1 THEN 1 ELSE 0 END), 4) AS payment_delay_rate,
            ROUND(AVG(CASE WHEN repayment_status >= 2 THEN 1 ELSE 0 END), 4) AS serious_delay_rate,
            ROUND(AVG(GREATEST(CAST(bill_amount AS DOUBLE), 0)), 2) AS avg_positive_bill_amount,
            ROUND(AVG(GREATEST(CAST(payment_amount AS DOUBLE), 0)), 2) AS avg_payment_amount,
            ROUND(
                AVG(
                    GREATEST(CAST(payment_amount AS DOUBLE), 0)
                    / NULLIF(GREATEST(CAST(bill_amount AS DOUBLE), 0), 0)
                ),
                4
            ) AS avg_payment_to_bill_ratio
        FROM monthly
        GROUP BY month_order, statement_month
        ORDER BY month_order;
    """


def concentration_hotspots_query() -> str:
    return f"""
        WITH segment_summary AS (
            SELECT
                credit_limit_segment,
                utilization_segment,
                repayment_behavior_category,
                primary_risk_reason,
                COUNT(*) AS customer_count,
                SUM(default_payment_next_month) AS defaulted_customers,
                AVG(default_payment_next_month) AS observed_default_rate,
                SUM(credit_line_exposure) AS total_credit_line_exposure,
                SUM(current_balance_exposure) AS total_current_balance_exposure,
                AVG(current_balance_exposure) AS avg_current_balance_exposure,
                AVG(avg_balance_exposure) AS avg_balance_exposure,
                AVG(utilization_clean) AS avg_utilization,
                AVG(avg_payment_amount) AS avg_payment_amount,
                AVG(months_with_payment_delay) AS avg_months_with_payment_delay,
                AVG(months_with_serious_delay) AS avg_months_with_serious_delay,
                SUM(revenue_proxy_6mo) AS total_revenue_proxy_6mo,
                SUM(realized_loss_proxy) AS total_realized_loss_proxy,
                SUM(observed_risk_adjusted_profit_proxy) AS total_rap_proxy
            FROM portfolio_enriched
            GROUP BY
                credit_limit_segment,
                utilization_segment,
                repayment_behavior_category,
                primary_risk_reason
            HAVING COUNT(*) >= {MIN_SEGMENT_SIZE}
        )

        SELECT
            credit_limit_segment,
            utilization_segment,
            repayment_behavior_category,
            primary_risk_reason,
            customer_count,
            defaulted_customers,
            ROUND(observed_default_rate, 4) AS observed_default_rate,
            ROUND(total_credit_line_exposure, 2) AS total_credit_line_exposure,
            ROUND(total_current_balance_exposure, 2) AS total_current_balance_exposure,
            ROUND(avg_current_balance_exposure, 2) AS avg_current_balance_exposure,
            ROUND(avg_balance_exposure, 2) AS avg_balance_exposure,
            ROUND(avg_utilization, 4) AS avg_utilization,
            ROUND(avg_payment_amount, 2) AS avg_payment_amount,
            ROUND(avg_months_with_payment_delay, 2) AS avg_months_with_payment_delay,
            ROUND(avg_months_with_serious_delay, 2) AS avg_months_with_serious_delay,
            ROUND(observed_default_rate * total_current_balance_exposure * {LGD_ASSUMPTION}, 2)
                AS total_expected_loss_proxy,
            ROUND(total_revenue_proxy_6mo, 2) AS total_revenue_proxy_6mo,
            ROUND(total_realized_loss_proxy, 2) AS total_realized_loss_proxy,
            ROUND(total_rap_proxy, 2) AS total_risk_adjusted_profit_proxy,
            CASE
                WHEN observed_default_rate >= 0.35 AND total_current_balance_exposure >= 10000000
                    THEN 'Critical risk concentration'
                WHEN observed_default_rate >= 0.30
                    THEN 'High default risk'
                WHEN total_current_balance_exposure >= 10000000
                    THEN 'High exposure concentration'
                ELSE 'Monitor'
            END AS concentration_risk_flag
        FROM segment_summary
        ORDER BY total_expected_loss_proxy DESC, observed_default_rate DESC, total_current_balance_exposure DESC;
    """


def assumption_sensitivity_query() -> str:
    return """
        WITH assumptions(lgd_assumption, revenue_rate_proxy) AS (
            VALUES
                (0.45, 0.06), (0.45, 0.09), (0.45, 0.12),
                (0.60, 0.06), (0.60, 0.09), (0.60, 0.12),
                (0.75, 0.06), (0.75, 0.09), (0.75, 0.12)
        ),

        portfolio_sensitivity AS (
            SELECT
                a.lgd_assumption,
                a.revenue_rate_proxy,
                COUNT(*) AS customer_count,
                AVG(default_payment_next_month) AS observed_default_rate,
                SUM(current_balance_exposure) AS total_current_balance_exposure,
                SUM(avg_balance_exposure) AS total_avg_balance_exposure,
                SUM(avg_balance_exposure * a.revenue_rate_proxy) AS total_revenue_proxy,
                SUM(default_payment_next_month * avg_balance_exposure * a.lgd_assumption)
                    AS total_realized_loss_proxy,
                SUM(avg_balance_exposure * a.revenue_rate_proxy)
                - SUM(default_payment_next_month * avg_balance_exposure * a.lgd_assumption)
                    AS total_risk_adjusted_profit_proxy
            FROM portfolio_enriched p
            CROSS JOIN assumptions a
            GROUP BY a.lgd_assumption, a.revenue_rate_proxy
        )

        SELECT
            lgd_assumption,
            revenue_rate_proxy,
            customer_count,
            ROUND(observed_default_rate, 4) AS observed_default_rate,
            ROUND(total_current_balance_exposure, 2) AS total_current_balance_exposure,
            ROUND(total_avg_balance_exposure, 2) AS total_avg_balance_exposure,
            ROUND(total_revenue_proxy, 2) AS total_revenue_proxy,
            ROUND(total_realized_loss_proxy, 2) AS total_realized_loss_proxy,
            ROUND(total_risk_adjusted_profit_proxy, 2) AS total_risk_adjusted_profit_proxy
        FROM portfolio_sensitivity
        ORDER BY lgd_assumption, revenue_rate_proxy;
    """


def segment_priority_score_query() -> str:
    return f"""
        WITH benchmark AS (
            SELECT
                AVG(default_payment_next_month) AS portfolio_default_rate,
                SUM(current_balance_exposure) AS portfolio_exposure
            FROM portfolio_enriched
        ),

        segment_summary AS (
            SELECT
                credit_limit_segment,
                utilization_segment,
                repayment_behavior_category,
                COUNT(*) AS customer_count,
                SUM(default_payment_next_month) AS defaulted_customers,
                AVG(default_payment_next_month) AS observed_default_rate,
                SUM(current_balance_exposure) AS total_current_balance_exposure,
                AVG(avg_balance_exposure) AS avg_balance_exposure,
                AVG(utilization_clean) AS avg_utilization,
                AVG(avg_payment_amount) AS avg_payment_amount,
                AVG(months_with_payment_delay) AS avg_months_with_payment_delay,
                AVG(months_with_serious_delay) AS avg_months_with_serious_delay,
                SUM(default_payment_next_month * avg_balance_exposure * {LGD_ASSUMPTION})
                    AS realized_loss_proxy,
                SUM(avg_balance_exposure * {SIX_MONTH_REVENUE_RATE_PROXY}) AS revenue_proxy,
                SUM(avg_balance_exposure * {SIX_MONTH_REVENUE_RATE_PROXY})
                - SUM(default_payment_next_month * avg_balance_exposure * {LGD_ASSUMPTION})
                    AS risk_adjusted_profit_proxy
            FROM portfolio_enriched
            GROUP BY credit_limit_segment, utilization_segment, repayment_behavior_category
            HAVING COUNT(*) >= {MIN_SEGMENT_SIZE}
        ),

        scored AS (
            SELECT
                s.*,
                b.portfolio_default_rate,
                s.observed_default_rate / NULLIF(b.portfolio_default_rate, 0) AS default_rate_lift,
                s.total_current_balance_exposure / NULLIF(b.portfolio_exposure, 0) AS exposure_share,
                s.realized_loss_proxy / NULLIF(SUM(s.realized_loss_proxy) OVER (), 0) AS loss_share,
                (
                    s.observed_default_rate / NULLIF(b.portfolio_default_rate, 0)
                )
                *
                (
                    s.total_current_balance_exposure / NULLIF(b.portfolio_exposure, 0)
                )
                * 100 AS segment_priority_score
            FROM segment_summary s
            CROSS JOIN benchmark b
        )

        SELECT
            credit_limit_segment,
            utilization_segment,
            repayment_behavior_category,
            customer_count,
            defaulted_customers,
            ROUND(observed_default_rate, 4) AS observed_default_rate,
            ROUND(portfolio_default_rate, 4) AS portfolio_default_rate,
            ROUND(default_rate_lift, 2) AS default_rate_lift,
            ROUND(total_current_balance_exposure, 2) AS total_current_balance_exposure,
            ROUND(exposure_share, 4) AS exposure_share,
            ROUND(loss_share, 4) AS loss_share,
            ROUND(avg_balance_exposure, 2) AS avg_balance_exposure,
            ROUND(avg_utilization, 4) AS avg_utilization,
            ROUND(avg_payment_amount, 2) AS avg_payment_amount,
            ROUND(avg_months_with_payment_delay, 2) AS avg_months_with_payment_delay,
            ROUND(avg_months_with_serious_delay, 2) AS avg_months_with_serious_delay,
            ROUND(revenue_proxy, 2) AS revenue_proxy,
            ROUND(realized_loss_proxy, 2) AS realized_loss_proxy,
            ROUND(risk_adjusted_profit_proxy, 2) AS risk_adjusted_profit_proxy,
            ROUND(segment_priority_score, 2) AS segment_priority_score,
            CASE
                WHEN segment_priority_score >= 5 AND observed_default_rate > portfolio_default_rate
                    THEN 'Immediate management review'
                WHEN observed_default_rate > portfolio_default_rate AND exposure_share >= 0.02
                    THEN 'Monitor and reprice'
                WHEN observed_default_rate <= portfolio_default_rate AND risk_adjusted_profit_proxy > 0
                    THEN 'Growth candidate'
                WHEN risk_adjusted_profit_proxy < 0
                    THEN 'Restrict or reduce exposure'
                ELSE 'Standard monitoring'
            END AS portfolio_strategy_flag
        FROM scored
        ORDER BY segment_priority_score DESC, realized_loss_proxy DESC, observed_default_rate DESC;
    """


def reconciliation_check_query() -> str:
    return """
        SELECT
            'portfolio_reconciliation' AS check_name,
            COUNT(*) AS customer_count,
            COUNT(DISTINCT customer_id) AS distinct_customer_ids,
            SUM(default_payment_next_month) AS defaulted_customers,
            COUNT(*) - SUM(default_payment_next_month) AS non_defaulted_customers,
            ROUND(AVG(default_payment_next_month), 4) AS portfolio_default_rate,
            ROUND(SUM(credit_line_exposure), 2) AS total_credit_line_exposure,
            ROUND(SUM(current_balance_exposure), 2) AS total_current_balance_exposure,
            ROUND(SUM(revenue_proxy_6mo), 2) AS total_revenue_proxy_6mo,
            ROUND(SUM(realized_loss_proxy), 2) AS total_realized_loss_proxy,
            ROUND(SUM(observed_risk_adjusted_profit_proxy), 2)
                AS total_observed_risk_adjusted_profit_proxy,
            CASE
                WHEN COUNT(*) = 30000
                 AND COUNT(DISTINCT customer_id) = 30000
                 AND SUM(default_payment_next_month) = 6636
                    THEN 'PASS'
                ELSE 'REVIEW'
            END AS reconciliation_status
        FROM portfolio_enriched;
    """


def tableau_customer_query() -> str:
    return """
        WITH portfolio_benchmark AS (
            SELECT
                AVG(default_payment_next_month) AS portfolio_default_rate,
                AVG(observed_risk_adjusted_profit_proxy) AS portfolio_avg_rap
            FROM portfolio_enriched
        )

        SELECT
            p.customer_id,
            p.credit_limit,
            p.age,
            p.age_group,
            p.sex_label,
            p.education_label,
            p.marriage_label,
            p.credit_limit_segment,
            p.utilization_segment,
            p.repayment_behavior_category,
            p.bill_statement_size_segment,
            p.payment_amount_segment,
            p.default_payment_next_month,
            p.credit_line_exposure,
            p.current_balance_exposure,
            p.avg_balance_exposure,
            p.utilization_clean,
            p.months_with_payment_delay,
            p.months_with_serious_delay,
            p.any_payment_delay_flag,
            p.serious_payment_delay_flag,
            p.avg_payment_amount,
            p.recent_payment_to_bill_ratio,
            p.revenue_proxy_6mo,
            p.realized_loss_proxy,
            p.observed_risk_adjusted_profit_proxy,
            p.approval_risk_band,
            p.primary_risk_reason,
            p.portfolio_monitoring_flag,
            CASE
                WHEN p.default_payment_next_month <= b.portfolio_default_rate
                 AND p.observed_risk_adjusted_profit_proxy >= b.portfolio_avg_rap
                    THEN 'Low-risk / high-profit'
                WHEN p.default_payment_next_month <= b.portfolio_default_rate
                 AND p.observed_risk_adjusted_profit_proxy < b.portfolio_avg_rap
                    THEN 'Low-risk / low-profit'
                WHEN p.default_payment_next_month > b.portfolio_default_rate
                 AND p.observed_risk_adjusted_profit_proxy >= b.portfolio_avg_rap
                    THEN 'High-risk / high-profit'
                ELSE 'High-risk / low-profit'
            END AS historical_customer_outcome_segment
        FROM portfolio_enriched p
        CROSS JOIN portfolio_benchmark b;
    """


def export_query(
    con: duckdb.DuckDBPyConnection,
    query_name: str,
    query: str,
    executed_sql: list[str],
) -> pd.DataFrame:
    logging.info("Running query: %s", query_name)

    df = con.execute(query).df()
    output_file = OUTPUT_DIR / f"{query_name}.csv"
    df.to_csv(output_file, index=False)

    executed_sql.append(f"-- {query_name}\n{query.strip()}\n\n")
    logging.info("Saved: %s", output_file)

    return df


def _safe_table_text(df: pd.DataFrame, columns: list[str]) -> str:
    existing_columns = [col for col in columns if col in df.columns]
    if not existing_columns:
        return "No matching columns available."
    if df.empty:
        return "No rows available."
    return df[existing_columns].to_string(index=False)


def create_executive_summary(
    overview_df: pd.DataFrame,
    segment_df: pd.DataFrame,
    hotspot_df: pd.DataFrame,
    priority_df: pd.DataFrame,
    reconciliation_df: pd.DataFrame,
) -> None:
    overview = overview_df.iloc[0]
    reconciliation = reconciliation_df.iloc[0]

    top_segments = (
        segment_df.sort_values(
            by=["avg_expected_loss_proxy", "observed_default_rate"],
            ascending=[False, False],
        )
        .head(10)
        .copy()
    )

    top_hotspots = hotspot_df.head(10).copy()
    top_priority = priority_df.head(10).copy()

    segment_cols = [
        "segmentation_type",
        "segment_name",
        "customer_count",
        "observed_default_rate",
        "default_rate_lift",
        "avg_expected_loss_proxy",
        "avg_risk_adjusted_profit_proxy",
        "risk_profit_segment",
        "recommended_action",
    ]

    hotspot_cols = [
        "credit_limit_segment",
        "utilization_segment",
        "repayment_behavior_category",
        "primary_risk_reason",
        "customer_count",
        "observed_default_rate",
        "total_expected_loss_proxy",
        "concentration_risk_flag",
    ]

    priority_cols = [
        "credit_limit_segment",
        "utilization_segment",
        "repayment_behavior_category",
        "customer_count",
        "observed_default_rate",
        "default_rate_lift",
        "exposure_share",
        "loss_share",
        "segment_priority_score",
        "portfolio_strategy_flag",
    ]

    top_segment_text = _safe_table_text(top_segments, segment_cols)
    hotspot_text = _safe_table_text(top_hotspots, hotspot_cols)
    priority_text = _safe_table_text(top_priority, priority_cols)

    summary = f"""# Executive SQL Summary

Project: Credit Risk & Customer Profitability Analytics
Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Portfolio Overview

- Customer count: {int(overview["customer_count"]):,}
- Defaulted customers: {int(overview["defaulted_customers"]):,}
- Non-defaulted customers: {int(overview["non_defaulted_customers"]):,}
- Portfolio default rate: {overview["portfolio_default_rate"]:.2%}
- Total credit line exposure: {overview["total_credit_line_exposure"]:,.2f}
- Total current balance exposure: {overview["total_current_balance_exposure"]:,.2f}
- Average credit limit: {overview["avg_credit_limit"]:,.2f}
- Average utilization: {overview["avg_utilization"]:.2%}
- Average six-month revenue proxy: {overview["avg_revenue_proxy_6mo"]:,.2f}
- Average realized loss proxy: {overview["avg_realized_loss_proxy"]:,.2f}
- Average observed risk-adjusted profit proxy: {overview["avg_observed_risk_adjusted_profit_proxy"]:,.2f}
- Portfolio monitoring flag rate: {overview["monitoring_flag_rate"]:.2%}

## Reconciliation Check

- Reconciliation status: {reconciliation["reconciliation_status"]}
- Customer count: {int(reconciliation["customer_count"]):,}
- Distinct customer IDs: {int(reconciliation["distinct_customer_ids"]):,}
- Defaulted customers: {int(reconciliation["defaulted_customers"]):,}
- Portfolio default rate: {reconciliation["portfolio_default_rate"]:.2%}

## Assumptions Used in SQL Layer

- Loss given default assumption: {LGD_ASSUMPTION:.0%}
- Six-month revenue rate proxy: {SIX_MONTH_REVENUE_RATE_PROXY:.0%}
- Minimum segment size for reporting: {MIN_SEGMENT_SIZE:,} customers

These are proxy assumptions because the public dataset does not include actual APR, interest income, fee income, recoveries, charge-off amount, or account-level profit.

## Highest Expected-Loss Segment Candidates

{top_segment_text}

## Highest Risk / Exposure Concentrations

{hotspot_text}

## Highest Segment Priority Scores

{priority_text}

## Analyst Interpretation

The SQL layer shows how observed default risk, exposure, estimated loss, revenue proxy, and risk-adjusted profitability vary across borrower segments.

The strongest risk indicators are expected to come from repayment history, utilization behavior, payment delay patterns, balance size, and recent payment activity.

This SQL analysis is intentionally historical. It uses observed default outcomes to understand portfolio behavior. The next modeling phase will replace observed default-rate proxies with borrower-level predicted probability of default.

## Governance Note

Demographic variables such as sex, education, and marital status should be treated as monitoring or fairness-review variables, not as direct approval, pricing, or rejection rules.

## Pipeline Position

This SQL layer establishes the portfolio baseline. The modeling layer uses this context to move from observed historical default patterns to borrower-level predicted default risk.
"""

    EXECUTIVE_SUMMARY_FILE.write_text(summary, encoding="utf-8")


def main() -> None:
    validate_input_file()

    con = duckdb.connect()
    con.execute("PRAGMA threads=4;")

    create_portfolio_view(con)

    executed_sql: list[str] = []

    overview_query = """
        SELECT
            COUNT(*) AS customer_count,
            SUM(default_payment_next_month) AS defaulted_customers,
            COUNT(*) - SUM(default_payment_next_month) AS non_defaulted_customers,
            AVG(default_payment_next_month) AS portfolio_default_rate,
            SUM(credit_line_exposure) AS total_credit_line_exposure,
            SUM(current_balance_exposure) AS total_current_balance_exposure,
            AVG(credit_limit) AS avg_credit_limit,
            AVG(current_balance_exposure) AS avg_current_balance_exposure,
            AVG(utilization_clean) AS avg_utilization,
            AVG(revenue_proxy_6mo) AS avg_revenue_proxy_6mo,
            AVG(realized_loss_proxy) AS avg_realized_loss_proxy,
            AVG(observed_risk_adjusted_profit_proxy) AS avg_observed_risk_adjusted_profit_proxy,
            AVG(CASE WHEN portfolio_monitoring_flag = 1 THEN 1.0 ELSE 0.0 END)
                AS monitoring_flag_rate
        FROM portfolio_enriched;
    """

    segment_specs = [
        ("02_age_group_risk_return", "age_group", "Age Group"),
        ("03_credit_limit_segment_risk_return", "credit_limit_segment", "Credit Limit Segment"),
        ("04_utilization_segment_risk_return", "utilization_segment", "Utilization Segment"),
        ("05_repayment_behavior_risk_return", "repayment_behavior_category", "Repayment Behavior"),
        ("06_bill_statement_size_risk_return", "bill_statement_size_segment", "Bill Statement Size"),
        ("07_payment_amount_risk_return", "payment_amount_segment", "Payment Amount"),
        ("08_monitoring_flag_risk_return", "portfolio_monitoring_flag", "Portfolio Monitoring Flag"),
        ("09_approval_risk_band_risk_return", "approval_risk_band", "Approval Risk Band"),
    ]

    print("=" * 80)
    print("Running portfolio SQL analysis...")
    print("=" * 80)

    overview_df = export_query(con, "01_portfolio_overview", overview_query, executed_sql)

    segment_frames = []
    for file_name, segment_column, segment_label in segment_specs:
        segment_df = export_query(
            con,
            file_name,
            segment_risk_return_query(segment_column, segment_label),
            executed_sql,
        )
        segment_frames.append(segment_df)

    segment_df_all = pd.concat(segment_frames, ignore_index=True)
    segment_df_all.to_csv(TABLEAU_SEGMENT_FILE, index=False)

    repayment_df = export_query(con, "10_monthly_repayment_history", repayment_history_query(), executed_sql)
    hotspot_df = export_query(con, "11_concentration_hotspots", concentration_hotspots_query(), executed_sql)
    customer_df = export_query(con, "12_tableau_customer_portfolio_base", tableau_customer_query(), executed_sql)
    customer_df.to_csv(TABLEAU_CUSTOMER_FILE, index=False)
    sensitivity_df = export_query(con, "13_assumption_sensitivity_analysis", assumption_sensitivity_query(), executed_sql)
    priority_df = export_query(con, "14_segment_priority_score", segment_priority_score_query(), executed_sql)
    reconciliation_df = export_query(con, "15_portfolio_reconciliation_check", reconciliation_check_query(), executed_sql)

    create_executive_summary(
        overview_df=overview_df,
        segment_df=segment_df_all,
        hotspot_df=hotspot_df,
        priority_df=priority_df,
        reconciliation_df=reconciliation_df,
    )

    SQL_LOG_FILE.write_text("\n".join(executed_sql), encoding="utf-8")

    print("=" * 80)
    print("SQL portfolio analysis completed successfully.")
    print("=" * 80)
    print(f"\nSQL outputs saved to:\n{OUTPUT_DIR}")
    print(f"\nTableau segment file saved to:\n{TABLEAU_SEGMENT_FILE}")
    print(f"\nTableau customer file saved to:\n{TABLEAU_CUSTOMER_FILE}")
    print(f"\nSQL log saved to:\n{SQL_LOG_FILE}")
    print(f"\nExecutive SQL summary saved to:\n{EXECUTIVE_SUMMARY_FILE}")

    print("\nPortfolio overview:")
    print(overview_df.T)
    print("\nTop concentration hotspots:")
    print(hotspot_df.head(10))
    print("\nAssumption sensitivity preview:")
    print(sensitivity_df.head(10))
    print("\nTop segment priority scores:")
    print(priority_df.head(10))
    print("\nReconciliation check:")
    print(reconciliation_df.T)

    _ = repayment_df


if __name__ == "__main__":
    main()