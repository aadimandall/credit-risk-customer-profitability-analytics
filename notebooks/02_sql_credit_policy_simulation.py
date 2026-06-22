"""
02_sql_credit_policy_simulation.py
Historical credit policy simulation layer for the Credit Risk & Customer
Profitability Analytics project.
This script compares baseline, conservative, balanced, and growth-oriented
credit policy strategies using the cleaned customer-level dataset. The goal is
to test how different approval, manual-review, and decline rules would have
changed approval volume, default concentration, exposure, revenue proxy, loss
proxy, and risk-adjusted profitability.
This is a retrospective policy simulation, not a production underwriting model.
The rules use observed historical outcomes and proxy profitability assumptions
because the public dataset does not include real pricing, recoveries, charge-offs,
or account-level profit.
"""

from pathlib import Path
from datetime import datetime
import logging

import duckdb
import pandas as pd

BASE = Path(__file__).resolve().parents[1]

INPUT_FILE = BASE / "data" / "processed" / "credit_card_default_analysis_ready.csv"
OUTPUT_DIR = BASE / "data" / "processed" / "policy_simulation_outputs"
SQL_DIR = BASE / "sql"

CUSTOMER_DECISIONS_FILE = OUTPUT_DIR / "credit_policy_customer_decisions.csv"
POLICY_SUMMARY_FILE = OUTPUT_DIR / "credit_policy_simulation_summary.csv"
POLICY_DECISION_MIX_FILE = OUTPUT_DIR / "credit_policy_decision_mix.csv"
POLICY_SEGMENT_FILE = OUTPUT_DIR / "credit_policy_segment_summary.csv"
POLICY_EXECUTIVE_SUMMARY_FILE = OUTPUT_DIR / "_credit_policy_simulation_summary.md"
SQL_LOG_FILE = SQL_DIR / "executed_credit_policy_simulation_queries.sql"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SQL_DIR.mkdir(parents=True, exist_ok=True)

#Public Dataset Limitation:
#The dataset does not inlude APR, charge-offs, recoveries, or true customer-level.
#profitability. I use these assumptions only to compare policy strategies directionally.
LGD_ASSUMPTION = 0.60
SIX_MONTH_REVENUE_RATE_PROXY = 0.09

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


def load_policy_base(con: duckdb.DuckDBPyConnection) -> None:
    logging.info("Loading analysis-ready dataset into DuckDB...")
    #This view adds the exposure, revenue, loss and policy-risk fields
    #across the simulated approval, review and decline strategies.
    con.execute(
        """
        CREATE OR REPLACE TABLE credit_card_portfolio AS
        SELECT *
        FROM read_csv_auto(?)
        """,
        [str(INPUT_FILE)],
    )

    logging.info("Creating policy simulation base view...")

    con.execute(
        f"""
        CREATE OR REPLACE VIEW policy_base AS
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
                WHEN serious_payment_delay_flag = 1 THEN 'Serious delinquency history'
                WHEN utilization_proxy >= 0.90 THEN 'High utilization'
                WHEN recent_payment_to_bill_ratio < 0.10 THEN 'Weak recent repayment'
                WHEN months_with_payment_delay >= 2 THEN 'Repeated payment delays'
                WHEN avg_payment_amount <= 0 THEN 'No meaningful payment activity'
                ELSE 'Lower observed risk indicators'
            END AS primary_policy_reason

        FROM credit_card_portfolio;
        """
    )


def customer_decision_query() -> str:
    return """
        WITH policy_decisions AS (
            SELECT
                '01_Current Baseline' AS policy_name,
                customer_id,
                'Approve' AS policy_decision,
                'Baseline approves full historical portfolio' AS decision_reason
            FROM policy_base

            UNION ALL

            SELECT
                '02_Conservative Risk Cut' AS policy_name,
                customer_id,
                CASE
                    WHEN serious_payment_delay_flag = 1 OR utilization_proxy >= 0.90
                        THEN 'Decline'
                    WHEN any_payment_delay_flag = 1
                      OR utilization_proxy >= 0.75
                      OR recent_payment_to_bill_ratio < 0.10
                        THEN 'Manual Review'
                    ELSE 'Approve'
                END AS policy_decision,
                CASE
                    WHEN serious_payment_delay_flag = 1
                        THEN 'Decline: serious payment delay history'
                    WHEN utilization_proxy >= 0.90
                        THEN 'Decline: utilization at or above 90%'
                    WHEN any_payment_delay_flag = 1
                        THEN 'Review: payment delay history'
                    WHEN utilization_proxy >= 0.75
                        THEN 'Review: utilization at or above 75%'
                    WHEN recent_payment_to_bill_ratio < 0.10
                        THEN 'Review: weak recent repayment'
                    ELSE 'Approve: lower observed risk indicators'
                END AS decision_reason
            FROM policy_base

            UNION ALL

            SELECT
                '03_Balanced Risk Policy' AS policy_name,
                customer_id,
                CASE
                    WHEN months_with_serious_delay >= 2 OR utilization_proxy >= 1.00
                        THEN 'Decline'
                    WHEN serious_payment_delay_flag = 1
                      OR months_with_payment_delay >= 2
                      OR utilization_proxy >= 0.90
                      OR recent_payment_to_bill_ratio < 0.10
                        THEN 'Manual Review'
                    ELSE 'Approve'
                END AS policy_decision,
                CASE
                    WHEN months_with_serious_delay >= 2
                        THEN 'Decline: repeated serious delays'
                    WHEN utilization_proxy >= 1.00
                        THEN 'Decline: over-limit or fully utilized'
                    WHEN serious_payment_delay_flag = 1
                        THEN 'Review: serious delay flag'
                    WHEN months_with_payment_delay >= 2
                        THEN 'Review: repeated payment delays'
                    WHEN utilization_proxy >= 0.90
                        THEN 'Review: high utilization'
                    WHEN recent_payment_to_bill_ratio < 0.10
                        THEN 'Review: weak recent repayment'
                    ELSE 'Approve: acceptable historical profile'
                END AS decision_reason
            FROM policy_base

            UNION ALL

            SELECT
                '04_Growth-Oriented Policy' AS policy_name,
                customer_id,
                CASE
                    WHEN months_with_serious_delay >= 3 AND utilization_proxy >= 0.90
                        THEN 'Decline'
                    WHEN serious_payment_delay_flag = 1 OR utilization_proxy >= 1.00
                        THEN 'Manual Review'
                    ELSE 'Approve'
                END AS policy_decision,
                CASE
                    WHEN months_with_serious_delay >= 3 AND utilization_proxy >= 0.90
                        THEN 'Decline: repeated serious delay and high utilization'
                    WHEN serious_payment_delay_flag = 1
                        THEN 'Review: serious delay flag'
                    WHEN utilization_proxy >= 1.00
                        THEN 'Review: over-limit or fully utilized'
                    ELSE 'Approve: growth policy accepts moderate risk'
                END AS decision_reason
            FROM policy_base
        )

        SELECT
            d.policy_name,
            d.policy_decision,
            d.decision_reason,

            p.customer_id,
            p.default_payment_next_month,

            p.credit_limit,
            p.credit_limit_segment,
            p.utilization_segment,
            p.repayment_behavior_category,
            p.bill_statement_size_segment,
            p.payment_amount_segment,

            p.age_group,
            p.sex_label,
            p.education_label,
            p.marriage_label,

            p.credit_line_exposure,
            p.current_balance_exposure,
            p.avg_balance_exposure,
            p.utilization_clean,

            p.months_with_payment_delay,
            p.months_with_serious_delay,
            p.any_payment_delay_flag,
            p.serious_payment_delay_flag,
            p.recent_payment_to_bill_ratio,

            p.revenue_proxy_6mo,
            p.realized_loss_proxy,
            p.observed_risk_adjusted_profit_proxy,
            p.primary_policy_reason

        FROM policy_decisions d
        INNER JOIN policy_base p
            ON d.customer_id = p.customer_id;
    """


def policy_summary_query() -> str:
    return """
        WITH decisions AS (
            SELECT *
            FROM policy_customer_decisions
        ),

        policy_rollup AS (
            SELECT
                policy_name,

                COUNT(*) AS total_customers,

                SUM(CASE WHEN policy_decision = 'Approve' THEN 1 ELSE 0 END)
                    AS approved_customers,

                SUM(CASE WHEN policy_decision = 'Manual Review' THEN 1 ELSE 0 END)
                    AS manual_review_customers,

                SUM(CASE WHEN policy_decision = 'Decline' THEN 1 ELSE 0 END)
                    AS declined_customers,

                AVG(CASE WHEN policy_decision = 'Approve' THEN 1.0 ELSE 0.0 END)
                    AS approval_rate,

                AVG(CASE WHEN policy_decision = 'Manual Review' THEN 1.0 ELSE 0.0 END)
                    AS manual_review_rate,

                AVG(CASE WHEN policy_decision = 'Decline' THEN 1.0 ELSE 0.0 END)
                    AS decline_rate,

                AVG(CASE WHEN policy_decision = 'Approve'
                         THEN default_payment_next_month
                         ELSE NULL END) AS approved_observed_default_rate,

                AVG(CASE WHEN policy_decision = 'Manual Review'
                         THEN default_payment_next_month
                         ELSE NULL END) AS manual_review_observed_default_rate,

                AVG(CASE WHEN policy_decision = 'Decline'
                         THEN default_payment_next_month
                         ELSE NULL END) AS declined_observed_default_rate,

                SUM(CASE WHEN policy_decision = 'Approve'
                         THEN current_balance_exposure
                         ELSE 0 END) AS approved_current_balance_exposure,

                SUM(CASE WHEN policy_decision = 'Manual Review'
                         THEN current_balance_exposure
                         ELSE 0 END) AS manual_review_current_balance_exposure,

                SUM(CASE WHEN policy_decision = 'Decline'
                         THEN current_balance_exposure
                         ELSE 0 END) AS declined_current_balance_exposure,

                SUM(CASE WHEN policy_decision = 'Approve'
                         THEN revenue_proxy_6mo
                         ELSE 0 END) AS approved_revenue_proxy_6mo,

                SUM(CASE WHEN policy_decision = 'Approve'
                         THEN realized_loss_proxy
                         ELSE 0 END) AS approved_realized_loss_proxy,

                SUM(CASE WHEN policy_decision = 'Approve'
                         THEN observed_risk_adjusted_profit_proxy
                         ELSE 0 END) AS approved_risk_adjusted_profit_proxy,

                SUM(CASE WHEN policy_decision = 'Decline'
                         THEN default_payment_next_month
                         ELSE 0 END) AS historical_defaults_avoided_by_decline,

                SUM(CASE WHEN policy_decision = 'Decline'
                         THEN realized_loss_proxy
                         ELSE 0 END) AS historical_loss_proxy_avoided_by_decline,

                SUM(CASE WHEN policy_decision = 'Decline'
                         THEN revenue_proxy_6mo
                         ELSE 0 END) AS revenue_proxy_given_up_by_decline

            FROM decisions
            GROUP BY policy_name
        )

        SELECT
            policy_name,

            total_customers,
            approved_customers,
            manual_review_customers,
            declined_customers,

            ROUND(approval_rate, 4) AS approval_rate,
            ROUND(manual_review_rate, 4) AS manual_review_rate,
            ROUND(decline_rate, 4) AS decline_rate,

            ROUND(approved_observed_default_rate, 4) AS approved_observed_default_rate,
            ROUND(manual_review_observed_default_rate, 4) AS manual_review_observed_default_rate,
            ROUND(declined_observed_default_rate, 4) AS declined_observed_default_rate,

            ROUND(approved_current_balance_exposure, 2) AS approved_current_balance_exposure,
            ROUND(manual_review_current_balance_exposure, 2) AS manual_review_current_balance_exposure,
            ROUND(declined_current_balance_exposure, 2) AS declined_current_balance_exposure,

            ROUND(approved_revenue_proxy_6mo, 2) AS approved_revenue_proxy_6mo,
            ROUND(approved_realized_loss_proxy, 2) AS approved_realized_loss_proxy,
            ROUND(approved_risk_adjusted_profit_proxy, 2) AS approved_risk_adjusted_profit_proxy,

            ROUND(historical_defaults_avoided_by_decline, 0)
                AS historical_defaults_avoided_by_decline,

            ROUND(historical_loss_proxy_avoided_by_decline, 2)
                AS historical_loss_proxy_avoided_by_decline,

            ROUND(revenue_proxy_given_up_by_decline, 2)
                AS revenue_proxy_given_up_by_decline,

            ROUND(
                historical_loss_proxy_avoided_by_decline
                - revenue_proxy_given_up_by_decline,
                2
            ) AS net_historical_value_of_declines_proxy,

            CASE
                WHEN approval_rate < 0.50
                    THEN 'Likely too restrictive; review approval impact'
                WHEN approved_observed_default_rate <= 0.18
                 AND approved_risk_adjusted_profit_proxy > 0
                    THEN 'Strong risk-return policy candidate'
                WHEN approved_observed_default_rate <= 0.22
                    THEN 'Balanced policy candidate'
                ELSE 'Higher-risk policy; monitor loss and exposure'
            END AS policy_interpretation

        FROM policy_rollup
        ORDER BY
            approved_risk_adjusted_profit_proxy DESC,
            approved_observed_default_rate ASC;
    """


def decision_mix_query() -> str:
    return """
        SELECT
            policy_name,
            policy_decision,

            COUNT(*) AS customer_count,
            ROUND(COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY policy_name), 4)
                AS decision_share,

            SUM(default_payment_next_month) AS defaulted_customers,
            ROUND(AVG(default_payment_next_month), 4) AS observed_default_rate,

            ROUND(SUM(current_balance_exposure), 2) AS current_balance_exposure,
            ROUND(SUM(revenue_proxy_6mo), 2) AS revenue_proxy_6mo,
            ROUND(SUM(realized_loss_proxy), 2) AS realized_loss_proxy,
            ROUND(SUM(observed_risk_adjusted_profit_proxy), 2)
                AS risk_adjusted_profit_proxy

        FROM policy_customer_decisions
        GROUP BY
            policy_name,
            policy_decision
        ORDER BY
            policy_name,
            CASE
                WHEN policy_decision = 'Approve' THEN 1
                WHEN policy_decision = 'Manual Review' THEN 2
                ELSE 3
            END;
    """


def segment_policy_query() -> str:
    return """
        SELECT
            policy_name,
            policy_decision,
            credit_limit_segment,
            utilization_segment,
            repayment_behavior_category,

            COUNT(*) AS customer_count,
            SUM(default_payment_next_month) AS defaulted_customers,
            ROUND(AVG(default_payment_next_month), 4) AS observed_default_rate,

            ROUND(SUM(current_balance_exposure), 2) AS current_balance_exposure,
            ROUND(AVG(utilization_clean), 4) AS avg_utilization,
            ROUND(AVG(months_with_payment_delay), 2) AS avg_months_with_payment_delay,
            ROUND(AVG(months_with_serious_delay), 2) AS avg_months_with_serious_delay,

            ROUND(SUM(revenue_proxy_6mo), 2) AS revenue_proxy_6mo,
            ROUND(SUM(realized_loss_proxy), 2) AS realized_loss_proxy,
            ROUND(SUM(observed_risk_adjusted_profit_proxy), 2)
                AS risk_adjusted_profit_proxy

        FROM policy_customer_decisions
        GROUP BY
            policy_name,
            policy_decision,
            credit_limit_segment,
            utilization_segment,
            repayment_behavior_category
        HAVING COUNT(*) >= 100
        ORDER BY
            policy_name,
            policy_decision,
            realized_loss_proxy DESC;
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


def create_policy_executive_summary(
    policy_summary_df: pd.DataFrame,
    decision_mix_df: pd.DataFrame,
) -> None:
    top_policy = policy_summary_df.iloc[0]

    lines = [
        "# Credit Policy Simulation Summary",
        "",
        "Project: Credit Risk & Customer Profitability Analytics",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Purpose",
        "",
        "This SQL layer simulates historical approval, manual-review, and decline policies using borrower repayment behavior, utilization, exposure, and observed default outcomes.",
        "",
        "This is a retrospective policy simulation. It is not a production underwriting model because it uses historical observed outcomes. The modeling layer later in the pipeline moves from observed default patterns to borrower-level predicted default risk.",
        "",
        "## Policy Scenarios Tested",
        "",
        "- 01_Current Baseline: approves the full historical portfolio.",
        "- 02_Conservative Risk Cut: declines serious payment delay or very high utilization cases.",
        "- 03_Balanced Risk Policy: declines repeated serious delays or over-limit utilization and sends moderate-risk cases to review.",
        "- 04_Growth-Oriented Policy: approves more borrowers while reviewing only the strongest risk signals.",
        "",
        "## Best Historical Policy by Approved Risk-Adjusted Profit Proxy",
        "",
        f"- Policy: {top_policy['policy_name']}",
        f"- Approval rate: {top_policy['approval_rate']:.2%}",
        f"- Approved observed default rate: {top_policy['approved_observed_default_rate']:.2%}",
        f"- Approved current balance exposure: {top_policy['approved_current_balance_exposure']:,.2f}",
        f"- Approved revenue proxy: {top_policy['approved_revenue_proxy_6mo']:,.2f}",
        f"- Approved realized loss proxy: {top_policy['approved_realized_loss_proxy']:,.2f}",
        f"- Approved risk-adjusted profit proxy: {top_policy['approved_risk_adjusted_profit_proxy']:,.2f}",
        f"- Interpretation: {top_policy['policy_interpretation']}",
        "",
        "## Files Created",
        "",
        "- credit_policy_customer_decisions.csv",
        "- credit_policy_simulation_summary.csv",
        "- credit_policy_decision_mix.csv",
        "- credit_policy_segment_summary.csv",
        "- executed_credit_policy_simulation_queries.sql",
        "",
        "## Governance Note",
        "",
        "Demographic fields are retained only for monitoring and fairness review. Policy rules should focus on repayment behavior, utilization, exposure, and payment behavior rather than protected or sensitive attributes.",
    ]

    POLICY_EXECUTIVE_SUMMARY_FILE.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    validate_input_file()

    con = duckdb.connect()
    con.execute("PRAGMA threads=4;")

    executed_sql: list[str] = []

    print("=" * 80)
    print("Running SQL credit policy simulation...")
    print("=" * 80)

    load_policy_base(con)

    customer_decisions_df = export_query(
        con,
        "credit_policy_customer_decisions",
        customer_decision_query(),
        executed_sql,
    )

    con.register("policy_customer_decisions_df", customer_decisions_df)
    con.execute(
        """
        CREATE OR REPLACE TABLE policy_customer_decisions AS
        SELECT *
        FROM policy_customer_decisions_df
        """
    )

    policy_summary_df = export_query(
        con,
        "credit_policy_simulation_summary",
        policy_summary_query(),
        executed_sql,
    )

    decision_mix_df = export_query(
        con,
        "credit_policy_decision_mix",
        decision_mix_query(),
        executed_sql,
    )

    segment_policy_df = export_query(
        con,
        "credit_policy_segment_summary",
        segment_policy_query(),
        executed_sql,
    )

    customer_decisions_df.to_csv(CUSTOMER_DECISIONS_FILE, index=False)
    policy_summary_df.to_csv(POLICY_SUMMARY_FILE, index=False)
    decision_mix_df.to_csv(POLICY_DECISION_MIX_FILE, index=False)
    segment_policy_df.to_csv(POLICY_SEGMENT_FILE, index=False)

    create_policy_executive_summary(policy_summary_df, decision_mix_df)

    SQL_LOG_FILE.write_text("\n".join(executed_sql), encoding="utf-8")

    print("=" * 80)
    print("SQL credit policy simulation completed successfully.")
    print("=" * 80)

    print(f"\nPolicy outputs saved to:\n{OUTPUT_DIR}")
    print(f"\nSQL log saved to:\n{SQL_LOG_FILE}")
    print(f"\nExecutive policy summary saved to:\n{POLICY_EXECUTIVE_SUMMARY_FILE}")

    print("\nPolicy summary:")
    print(policy_summary_df)

    print("\nDecision mix:")
    print(decision_mix_df)

    print("\nTop policy segment rows:")
    print(segment_policy_df.head(10))


if __name__ == "__main__":
    main()
    