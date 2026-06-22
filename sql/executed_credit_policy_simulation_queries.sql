-- credit_policy_customer_decisions
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


-- credit_policy_simulation_summary
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


-- credit_policy_decision_mix
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


-- credit_policy_segment_summary
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

