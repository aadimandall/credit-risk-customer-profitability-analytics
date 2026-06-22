-- 03_segment_analysis.sql
-- Purpose: Analyze default risk and exposure across borrower segments.

SELECT
    COUNT(*) AS customer_count,
    SUM(credit_limit) AS total_portfolio_exposure,
    AVG(default_payment_next_month) AS portfolio_default_rate,
    AVG(credit_limit) AS avg_credit_limit
FROM credit_card_features;

SELECT
    age_group,
    COUNT(*) AS customers,
    AVG(default_payment_next_month) AS default_rate,
    AVG(credit_limit) AS avg_credit_limit,
    SUM(credit_limit) AS total_exposure
FROM credit_card_features
GROUP BY age_group
ORDER BY default_rate DESC;

SELECT
    credit_limit_segment,
    COUNT(*) AS customers,
    AVG(default_payment_next_month) AS default_rate,
    AVG(credit_limit) AS avg_credit_limit,
    SUM(credit_limit) AS total_exposure
FROM credit_card_features
GROUP BY credit_limit_segment
ORDER BY default_rate DESC;

SELECT
    utilization_segment,
    COUNT(*) AS customers,
    AVG(default_payment_next_month) AS default_rate,
    AVG(utilization_proxy) AS avg_utilization_proxy,
    SUM(credit_limit) AS total_exposure
FROM credit_card_features
GROUP BY utilization_segment
ORDER BY default_rate DESC;

SELECT
    repayment_behavior_category,
    COUNT(*) AS customers,
    AVG(default_payment_next_month) AS default_rate,
    SUM(credit_limit) AS total_exposure
FROM credit_card_features
GROUP BY repayment_behavior_category
ORDER BY default_rate DESC;

SELECT
    credit_limit_segment,
    utilization_segment,
    repayment_behavior_category,
    COUNT(*) AS customers,
    AVG(default_payment_next_month) AS default_rate,
    SUM(credit_limit) AS total_exposure
FROM credit_card_features
GROUP BY
    credit_limit_segment,
    utilization_segment,
    repayment_behavior_category
HAVING COUNT(*) >= 100
ORDER BY default_rate DESC, total_exposure DESC;
