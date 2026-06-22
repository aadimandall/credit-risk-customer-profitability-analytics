# Executive Validation and Governance Summary

Project: Credit Risk & Customer Profitability Analytics
Generated: 2026-06-22 14:45:47

## Purpose

This layer validates the credit-risk model beyond basic accuracy metrics. It tests calibration, risk ranking, threshold tradeoffs, business impact, segment behavior, and fairness-monitoring indicators.

## Portfolio-Level Validation

- Customer records scored: 30,000
- Portfolio observed default rate: 22.12%
- Average predicted default probability: 22.12%
- Calibration gap: 0.00%
- Brier score: 0.1223
- Top-risk decile default rate: 75.03%
- Bottom-risk decile default rate: 1.63%
- Top-risk decile lift vs portfolio: 3.39x

## Risk Decile Business Impact

- Highest-risk decile customer count: 3,000
- Highest-risk decile observed default rate: 75.03%
- Highest-risk decile default capture rate: 33.92%
- Highest-risk decile actual loss capture rate: 44.98%

## Recommended Operating Threshold

- Recommended threshold: 0.150
- Threshold label: Balanced threshold
- Approval rate: 50.06%
- Flag rate: 49.94%
- Approved observed default rate: 6.02%
- Historical default capture rate: 86.38%
- Approved predicted risk-adjusted profitability proxy: 33,358,005.13

## Highest-Risk Segment Monitoring Candidates

- repayment_behavior_category = Repeated serious delay: default rate 56.37%, default-rate lift 2.55x, avg predicted PD 55.97%
- credit_limit_segment = Low limit: default rate 36.07%, default-rate lift 1.63x, avg predicted PD 35.76%
- repayment_behavior_category = Recent serious delay: default rate 32.23%, default-rate lift 1.46x, avg predicted PD 32.37%
- payment_amount_segment = Low payment: default rate 31.16%, default-rate lift 1.41x, avg predicted PD 31.01%
- utilization_segment = Over limit / very high utilization: default rate 30.07%, default-rate lift 1.36x, avg predicted PD 30.34%
- age_group = Under 25: default rate 27.19%, default-rate lift 1.23x, avg predicted PD 27.43%
- age_group = 55+: default rate 26.69%, default-rate lift 1.21x, avg predicted PD 26.94%
- payment_amount_segment = Medium payment: default rate 26.08%, default-rate lift 1.18x, avg predicted PD 25.75%

## Fairness and Governance Monitoring

- marriage_label = Other: Review flag-rate disparity; flag-rate difference vs portfolio 16.62%; calibration gap -0.21%
- age_group = Under 25: Review flag-rate disparity; flag-rate difference vs portfolio 14.56%; calibration gap 0.24%
- education_label = Other: Review flag-rate disparity; flag-rate difference vs portfolio -23.11%; calibration gap 7.18%
- education_label = Unknown: Review flag-rate disparity; flag-rate difference vs portfolio -34.00%; calibration gap 3.07%

## Files Created

- model_validation_summary.csv
- calibration_by_probability_band.csv
- risk_decile_business_summary.csv
- threshold_business_impact.csv
- segment_model_monitoring.csv
- fairness_monitoring_summary.csv
- model_error_analysis.csv
- model_governance_checklist.csv

## Governance Note

This project uses demographic fields only for monitoring and fairness review. They should not be framed as direct approval, pricing, or rejection rules. A production model would require stronger validation, regulatory review, adverse action reason codes, bias testing, monitoring over time, and model risk management approval.

## Analyst Takeaway

The model is useful not just because it predicts default, but because it ranks customers into actionable risk tiers, identifies where calibration should be monitored, links predicted probability to expected loss and profitability proxies, and supports threshold decisions that balance approval volume against credit risk.