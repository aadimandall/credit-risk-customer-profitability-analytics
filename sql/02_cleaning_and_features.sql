-- 02_cleaning_and_features.sql
-- Purpose: Create borrower-level segmentation fields for SQL analysis.

CREATE TABLE credit_card_features AS
SELECT
    *,
    CASE
        WHEN age < 25 THEN 'Under 25'
        WHEN age BETWEEN 25 AND 34 THEN '25-34'
        WHEN age BETWEEN 35 AND 44 THEN '35-44'
        WHEN age BETWEEN 45 AND 54 THEN '45-54'
        ELSE '55+'
    END AS age_group,

    CASE
        WHEN credit_limit < 50000 THEN 'Low limit'
        WHEN credit_limit BETWEEN 50000 AND 199999 THEN 'Mid limit'
        WHEN credit_limit BETWEEN 200000 AND 499999 THEN 'High limit'
        ELSE 'Very high limit'
    END AS credit_limit_segment,

    CASE
        WHEN repay_status_sep >= 1 OR repay_status_aug >= 1 OR repay_status_jul >= 1
          OR repay_status_jun >= 1 OR repay_status_may >= 1 OR repay_status_apr >= 1
        THEN 1 ELSE 0
    END AS any_payment_delay_flag,

    CASE
        WHEN repay_status_sep >= 2 OR repay_status_aug >= 2 OR repay_status_jul >= 2
          OR repay_status_jun >= 2 OR repay_status_may >= 2 OR repay_status_apr >= 2
        THEN 1 ELSE 0
    END AS serious_payment_delay_flag,

    CASE
        WHEN credit_limit <= 0 THEN NULL
        ELSE bill_amt_sep * 1.0 / credit_limit
    END AS utilization_proxy,

    CASE
        WHEN credit_limit <= 0 THEN 'Unknown'
        WHEN bill_amt_sep * 1.0 / credit_limit < 0.25 THEN 'Low utilization'
        WHEN bill_amt_sep * 1.0 / credit_limit < 0.75 THEN 'Medium utilization'
        ELSE 'High utilization'
    END AS utilization_segment,

    CASE
        WHEN pay_amt_sep = 0 THEN 'No recent payment'
        WHEN bill_amt_aug <= 0 THEN 'Payment made'
        WHEN pay_amt_sep * 1.0 / NULLIF(bill_amt_aug, 0) < 0.10 THEN 'Low repayment'
        WHEN pay_amt_sep * 1.0 / NULLIF(bill_amt_aug, 0) < 0.50 THEN 'Partial repayment'
        ELSE 'Strong repayment'
    END AS repayment_behavior_category

FROM credit_card_default_clean;
