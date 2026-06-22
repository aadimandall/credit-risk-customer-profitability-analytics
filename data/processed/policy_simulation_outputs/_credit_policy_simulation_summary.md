# Credit Policy Simulation Summary

Project: Credit Risk & Customer Profitability Analytics
Generated: 2026-06-22 14:45:38

## Purpose

This SQL layer simulates historical approval, manual-review, and decline policies using borrower repayment behavior, utilization, exposure, and observed default outcomes.

This is a retrospective policy simulation. It is not a production underwriting model because it uses historical observed outcomes. The modeling layer later in the pipeline moves from observed default patterns to borrower-level predicted default risk.

## Policy Scenarios Tested

- 01_Current Baseline: approves the full historical portfolio.
- 02_Conservative Risk Cut: declines serious payment delay or very high utilization cases.
- 03_Balanced Risk Policy: declines repeated serious delays or over-limit utilization and sends moderate-risk cases to review.
- 04_Growth-Oriented Policy: approves more borrowers while reviewing only the strongest risk signals.

## Best Historical Policy by Approved Risk-Adjusted Profit Proxy

- Policy: 04_Growth-Oriented Policy
- Approval rate: 67.83%
- Approved observed default rate: 12.44%
- Approved current balance exposure: 949,558,195.00
- Approved revenue proxy: 74,693,550.00
- Approved realized loss proxy: 45,040,959.10
- Approved risk-adjusted profit proxy: 29,652,590.90
- Interpretation: Strong risk-return policy candidate

## Files Created

- credit_policy_customer_decisions.csv
- credit_policy_simulation_summary.csv
- credit_policy_decision_mix.csv
- credit_policy_segment_summary.csv
- executed_credit_policy_simulation_queries.sql

## Governance Note

Demographic fields are retained only for monitoring and fairness review. Policy rules should focus on repayment behavior, utilization, exposure, and payment behavior rather than protected or sensitive attributes.