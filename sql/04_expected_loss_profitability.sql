-- 04_expected_loss_profitability.sql
-- Purpose: Create expected loss and risk-adjusted profitability framework.
-- Replace assumptions with final business assumptions later.

CREATE TABLE borrower_profitability_framework AS
SELECT
    customer_id,
    credit_limit,
    age_group,
    credit_limit_segment,
    utilization_segment,
    repayment_behavior_category,
    default_payment_next_month,

    credit_limit AS exposure_proxy,
    0.60 AS lgd_assumption,
    credit_limit * 0.03 AS estimated_revenue_proxy,
    default_payment_next_month * credit_limit * 0.60 AS observed_expected_loss_proxy,
    (credit_limit * 0.03) - (default_payment_next_month * credit_limit * 0.60) AS observed_risk_adjusted_profit_proxy,

    CASE
        WHEN default_payment_next_month = 0 AND ((credit_limit * 0.03) - (default_payment_next_month * credit_limit * 0.60)) >= 0
            THEN 'Low-risk / high-profit'
        WHEN default_payment_next_month = 0 AND ((credit_limit * 0.03) - (default_payment_next_month * credit_limit * 0.60)) < 0
            THEN 'Low-risk / low-profit'
        WHEN default_payment_next_month = 1 AND ((credit_limit * 0.03) - (default_payment_next_month * credit_limit * 0.60)) >= 0
            THEN 'High-risk / high-profit'
        ELSE 'High-risk / low-profit'
    END AS risk_profit_segment

FROM credit_card_features;
