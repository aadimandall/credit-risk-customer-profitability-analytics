# Executive Model Summary

Project: Credit Risk & Customer Profitability Analytics
Generated: 2026-06-22 14:45:46

## Purpose

This Python modeling layer estimates borrower-level probability of default and converts model scores into expected loss, revenue proxy, and risk-adjusted profitability proxy outputs.

## Dataset Split

- Training records: 24,000
- Test records: 6,000
- Test size: 20%
- Stratified split: Yes

## Best Model

- Selected model: hist_gradient_boosting
- ROC-AUC: 0.7788
- PR-AUC: 0.5567
- Accuracy at 0.50 threshold: 0.8178
- Recall at 0.50 threshold: 0.3640
- Precision at 0.50 threshold: 0.6598

## Lift Analysis

- Highest-risk decile observed default rate: 69.67%
- Portfolio test default rate: 22.12%
- Highest-risk decile lift vs portfolio: 3.15x

## Top Model Drivers

- 1. max_repayment_delay: 0.058260
- 2. repay_status_sep: 0.022926
- 3. utilization_proxy: 0.011716
- 4. bill_amt_sep: 0.008898
- 5. credit_limit: 0.006943
- 6. avg_payment_amount: 0.005324
- 7. avg_bill_amount: 0.005106
- 8. pay_amt_aug: 0.003347
- 9. pay_amt_sep: 0.002805
- 10. pay_amt_jul: 0.002562

## Files Created

- model_comparison.csv
- model_metrics.json
- threshold_analysis.csv
- lift_by_decile.csv
- feature_importance.csv
- credit_risk_scored_customers.csv
- credit_default_probability_model.joblib

## Governance Note

This model is for portfolio analytics and project demonstration. Demographic fields should be handled carefully and reviewed for fairness before any production credit decisioning use.

## Next Step

Use the scored customer output in Tableau to visualize predicted probability of default, expected loss proxy, risk-adjusted profitability proxy, risk deciles, and recommended portfolio strategy.