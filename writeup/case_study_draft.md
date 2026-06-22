# 1-Page Case Study Draft

## Project
Credit Risk & Customer Profitability Analytics

## Business Problem
A lender needs to understand which credit card borrowers create the greatest default risk, expected loss, and profitability opportunity. Approval strategy should not be based only on default risk. It should also consider exposure, expected loss, and risk-adjusted profitability.

## Data
The project uses 30,000 anonymized credit card customer records with credit limit, demographics, repayment status, bill statement amounts, payment amounts, and default outcome.

## Approach
SQL was used to clean and structure customer-level data, rename confusing columns, create borrower segments, and analyze default rate and exposure patterns. Python was used to build a default-risk classification model and calculate model performance. Expected loss was estimated using probability of default, exposure, and loss-given-default assumptions. Tableau was used to create an executive dashboard summarizing portfolio exposure, default probability, expected loss, profitability, and recommended actions by segment.

## Segmentation Framework

| Segment | Meaning | Action |
|---|---|---|
| Low-risk / high-profit | Strong risk-return profile | Prioritize |
| Low-risk / low-profit | Safe but low upside | Maintain efficiently |
| High-risk / high-profit | Profitable but risky | Monitor or reprice |
| High-risk / low-profit | Weak risk-return profile | Avoid or restrict |

## Model Results
Add actual metrics after running the model:
- ROC-AUC:
- Accuracy:
- Recall:
- Precision:
- Confusion matrix:

## Business Recommendations
- Prioritize low-risk / high-profit customers for growth and retention.
- Maintain low-risk / low-profit customers through efficient servicing.
- Monitor or reprice high-risk / high-profit customers because revenue potential exists but loss exposure is elevated.
- Restrict, decline, or reduce exposure to high-risk / low-profit customers.
- Use repayment history, credit utilization, bill statement size, and recent payment behavior as key monitoring indicators.

## Final Resume Version
Add only verified model metrics after the Python model is complete.
