-- 01_schema_and_import.sql
-- Purpose: Create a clean working table for the credit risk project.
-- After importing the raw dataset, rename the raw table to credit_card_default_raw.

CREATE TABLE credit_card_default_clean AS
SELECT
    ID AS customer_id,
    LIMIT_BAL AS credit_limit,
    SEX AS sex,
    EDUCATION AS education,
    MARRIAGE AS marriage,
    AGE AS age,
    PAY_0 AS repay_status_sep,
    PAY_2 AS repay_status_aug,
    PAY_3 AS repay_status_jul,
    PAY_4 AS repay_status_jun,
    PAY_5 AS repay_status_may,
    PAY_6 AS repay_status_apr,
    BILL_AMT1 AS bill_amt_sep,
    BILL_AMT2 AS bill_amt_aug,
    BILL_AMT3 AS bill_amt_jul,
    BILL_AMT4 AS bill_amt_jun,
    BILL_AMT5 AS bill_amt_may,
    BILL_AMT6 AS bill_amt_apr,
    PAY_AMT1 AS pay_amt_sep,
    PAY_AMT2 AS pay_amt_aug,
    PAY_AMT3 AS pay_amt_jul,
    PAY_AMT4 AS pay_amt_jun,
    PAY_AMT5 AS pay_amt_may,
    PAY_AMT6 AS pay_amt_apr,
    "default payment next month" AS default_payment_next_month
FROM credit_card_default_raw;
