# Executive SQL Summary

Project: Credit Risk & Customer Profitability Analytics
Generated: 2026-06-22 14:45:35

## Portfolio Overview

- Customer count: 30,000
- Defaulted customers: 6,636
- Non-defaulted customers: 23,364
- Portfolio default rate: 22.12%
- Total credit line exposure: 5,024,529,680.00
- Total current balance exposure: 1,537,381,257.00
- Average credit limit: 167,484.32
- Average utilization: 42.39%
- Average six-month revenue proxy: 4,048.96
- Average realized loss proxy: 5,772.33
- Average observed risk-adjusted profit proxy: -1,723.37
- Portfolio monitoring flag rate: 41.26%

## Reconciliation Check

- Reconciliation status: PASS
- Customer count: 30,000
- Distinct customer IDs: 30,000
- Defaulted customers: 6,636
- Portfolio default rate: 22.12%

## Assumptions Used in SQL Layer

- Loss given default assumption: 60%
- Six-month revenue rate proxy: 9%
- Minimum segment size for reporting: 100 customers

These are proxy assumptions because the public dataset does not include actual APR, interest income, fee income, recoveries, charge-off amount, or account-level profit.

## Highest Expected-Loss Segment Candidates

        segmentation_type                       segment_name  customer_count  observed_default_rate  default_rate_lift  avg_expected_loss_proxy  avg_risk_adjusted_profit_proxy    risk_profit_segment                                                recommended_action
      Utilization Segment Over limit / very high utilization            2115                 0.3007               1.36                 16999.06                        -8519.57 High-risk / low-profit Restrict, reduce exposure, or require stronger repayment behavior
       Repayment Behavior             Repeated serious delay            4886                 0.5637               2.55                 16168.92                       -11866.02 High-risk / low-profit Restrict, reduce exposure, or require stronger repayment behavior
      Bill Statement Size                    Very large bill            7500                 0.2049               0.93                 15996.74                        -4288.00  Low-risk / low-profit        Maintain efficiently; do not over-invest acquisition spend
Portfolio Monitoring Flag                                  1           12378                 0.3627               1.64                 13361.47                        -7835.02 High-risk / low-profit Restrict, reduce exposure, or require stronger repayment behavior
       Approval Risk Band                 High approval risk            8380                 0.4630               2.09                 13030.84                        -8809.25 High-risk / low-profit Restrict, reduce exposure, or require stronger repayment behavior
      Utilization Segment                   High utilization            6680                 0.2582               1.17                 12580.14                        -5272.72 High-risk / low-profit Restrict, reduce exposure, or require stronger repayment behavior
       Repayment Behavior               Recent serious delay            3494                 0.3223               1.46                  8825.55                        -4717.67 High-risk / low-profit Restrict, reduce exposure, or require stronger repayment behavior
      Utilization Segment                 Medium utilization            7167                 0.2385               1.08                  8656.67                        -3211.17 High-risk / low-profit Restrict, reduce exposure, or require stronger repayment behavior
       Approval Risk Band              Utilization watchlist            3989                 0.1524               0.69                  8394.92                         -133.24 Low-risk / high-profit                      Prioritize growth, retention, and cross-sell
                Age Group                                55+            1053                 0.2669               1.21                  7736.77                        -3387.93 High-risk / low-profit Restrict, reduce exposure, or require stronger repayment behavior

## Highest Risk / Exposure Concentrations

credit_limit_segment                utilization_segment repayment_behavior_category         primary_risk_reason  customer_count  observed_default_rate  total_expected_loss_proxy     concentration_risk_flag
           Mid limit                   High utilization      Repeated serious delay Serious delinquency history             733                 0.5607                19952392.88 Critical risk concentration
           Mid limit                 Medium utilization      Repeated serious delay Serious delinquency history             974                 0.5924                15904696.00 Critical risk concentration
          High limit                   High utilization      Repeated serious delay Serious delinquency history             147                 0.6327                12419721.06 Critical risk concentration
           Mid limit                   High utilization    Partial recent repayment            High utilization            1765                 0.1360                12313788.78 High exposure concentration
          High limit                   High utilization    Partial recent repayment            High utilization             479                 0.1399                10520030.15 High exposure concentration
           Mid limit Over limit / very high utilization      Repeated serious delay Serious delinquency history             282                 0.5887                 9317427.42 Critical risk concentration
           Mid limit Over limit / very high utilization    Partial recent repayment            High utilization             834                 0.1691                 8561091.22 High exposure concentration
           Mid limit                   High utilization        Recent serious delay Serious delinquency history             500                 0.3520                 8422359.69 Critical risk concentration
          High limit                 Medium utilization      Repeated serious delay Serious delinquency history             173                 0.5723                 8038474.27 Critical risk concentration
          High limit Over limit / very high utilization    Partial recent repayment            High utilization             212                 0.1840                 7337697.83 High exposure concentration

## Highest Segment Priority Scores

credit_limit_segment                utilization_segment repayment_behavior_category  customer_count  observed_default_rate  default_rate_lift  exposure_share  loss_share  segment_priority_score     portfolio_strategy_flag
           Mid limit                   High utilization      Repeated serious delay             733                 0.5607               2.53          0.0386      0.1246                    9.78 Immediate management review
           Mid limit                 Medium utilization      Repeated serious delay             974                 0.5924               2.68          0.0291      0.1052                    7.79 Immediate management review
           Mid limit                   High utilization    Partial recent repayment            2542                 0.1239               0.56          0.1382      0.0752                    7.74            Growth candidate
          High limit                   High utilization    Partial recent repayment             798                 0.1228               0.56          0.1304      0.0835                    7.24            Growth candidate
          High limit                   High utilization      Repeated serious delay             147                 0.6327               2.86          0.0213      0.0734                    6.09 Immediate management review
           Mid limit Over limit / very high utilization      Repeated serious delay             282                 0.5887               2.66          0.0172      0.0503                    4.57 Restrict or reduce exposure
           Mid limit Over limit / very high utilization    Partial recent repayment             834                 0.1691               0.76          0.0549      0.0376                    4.20 Restrict or reduce exposure
           Mid limit                   High utilization        Recent serious delay             500                 0.3520               1.59          0.0259      0.0430                    4.13         Monitor and reprice
          High limit                 Medium utilization      Repeated serious delay             173                 0.5723               2.59          0.0152      0.0489                    3.94 Restrict or reduce exposure
          High limit Over limit / very high utilization    Partial recent repayment             212                 0.1840               0.83          0.0432      0.0367                    3.60 Restrict or reduce exposure

## Analyst Interpretation

The SQL layer shows how observed default risk, exposure, estimated loss, revenue proxy, and risk-adjusted profitability vary across borrower segments.

The strongest risk indicators are expected to come from repayment history, utilization behavior, payment delay patterns, balance size, and recent payment activity.

This SQL analysis is intentionally historical. It uses observed default outcomes to understand portfolio behavior. The next modeling phase will replace observed default-rate proxies with borrower-level predicted probability of default.

## Governance Note

Demographic variables such as sex, education, and marital status should be treated as monitoring or fairness-review variables, not as direct approval, pricing, or rejection rules.

## Pipeline Position

This SQL layer establishes the portfolio baseline. The modeling layer uses this context to move from observed historical default patterns to borrower-level predicted default risk.
