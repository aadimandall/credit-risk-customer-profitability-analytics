-- 01_portfolio_overview
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


-- 02_age_group_risk_return
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
                'Age Group' AS segmentation_type,
                COALESCE(CAST(age_group AS VARCHAR), 'Unknown') AS segment_name,

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
            GROUP BY age_group
            HAVING COUNT(*) >= 100
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
                    * 0.6 AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * 0.09 AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * 0.09
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * 0.6
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


-- 03_credit_limit_segment_risk_return
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
                'Credit Limit Segment' AS segmentation_type,
                COALESCE(CAST(credit_limit_segment AS VARCHAR), 'Unknown') AS segment_name,

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
            GROUP BY credit_limit_segment
            HAVING COUNT(*) >= 100
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
                    * 0.6 AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * 0.09 AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * 0.09
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * 0.6
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


-- 04_utilization_segment_risk_return
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
                'Utilization Segment' AS segmentation_type,
                COALESCE(CAST(utilization_segment AS VARCHAR), 'Unknown') AS segment_name,

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
            GROUP BY utilization_segment
            HAVING COUNT(*) >= 100
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
                    * 0.6 AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * 0.09 AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * 0.09
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * 0.6
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


-- 05_repayment_behavior_risk_return
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
                'Repayment Behavior' AS segmentation_type,
                COALESCE(CAST(repayment_behavior_category AS VARCHAR), 'Unknown') AS segment_name,

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
            GROUP BY repayment_behavior_category
            HAVING COUNT(*) >= 100
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
                    * 0.6 AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * 0.09 AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * 0.09
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * 0.6
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


-- 06_bill_statement_size_risk_return
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
                'Bill Statement Size' AS segmentation_type,
                COALESCE(CAST(bill_statement_size_segment AS VARCHAR), 'Unknown') AS segment_name,

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
            GROUP BY bill_statement_size_segment
            HAVING COUNT(*) >= 100
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
                    * 0.6 AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * 0.09 AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * 0.09
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * 0.6
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


-- 07_payment_amount_risk_return
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
                'Payment Amount' AS segmentation_type,
                COALESCE(CAST(payment_amount_segment AS VARCHAR), 'Unknown') AS segment_name,

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
            GROUP BY payment_amount_segment
            HAVING COUNT(*) >= 100
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
                    * 0.6 AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * 0.09 AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * 0.09
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * 0.6
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


-- 08_monitoring_flag_risk_return
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
                'Portfolio Monitoring Flag' AS segmentation_type,
                COALESCE(CAST(portfolio_monitoring_flag AS VARCHAR), 'Unknown') AS segment_name,

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
            GROUP BY portfolio_monitoring_flag
            HAVING COUNT(*) >= 100
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
                    * 0.6 AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * 0.09 AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * 0.09
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * 0.6
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


-- 09_approval_risk_band_risk_return
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
                'Approval Risk Band' AS segmentation_type,
                COALESCE(CAST(approval_risk_band AS VARCHAR), 'Unknown') AS segment_name,

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
            GROUP BY approval_risk_band
            HAVING COUNT(*) >= 100
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
                    * 0.6 AS avg_expected_loss_proxy,

                s.avg_balance_exposure
                    * 0.09 AS avg_revenue_proxy_6mo,

                (
                    s.avg_balance_exposure
                    * 0.09
                )
                -
                (
                    s.observed_default_rate
                    * s.avg_balance_exposure
                    * 0.6
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


-- 10_monthly_repayment_history
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


-- 11_concentration_hotspots
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
            HAVING COUNT(*) >= 100
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
            ROUND(observed_default_rate * total_current_balance_exposure * 0.6, 2)
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


-- 12_tableau_customer_portfolio_base
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


-- 13_assumption_sensitivity_analysis
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


-- 14_segment_priority_score
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
                SUM(default_payment_next_month * avg_balance_exposure * 0.6)
                    AS realized_loss_proxy,
                SUM(avg_balance_exposure * 0.09) AS revenue_proxy,
                SUM(avg_balance_exposure * 0.09)
                - SUM(default_payment_next_month * avg_balance_exposure * 0.6)
                    AS risk_adjusted_profit_proxy
            FROM portfolio_enriched
            GROUP BY credit_limit_segment, utilization_segment, repayment_behavior_category
            HAVING COUNT(*) >= 100
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


-- 15_portfolio_reconciliation_check
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

