# Credit Risk & Customer Profitability Analytics

**End-to-end credit risk analytics project combining SQL portfolio analysis, Python machine learning, policy simulation, validation, governance, and Tableau executive reporting.** 

**Timeline: Apr 2026 – June 2026**
**Tools: Python, SQL, DuckDB, pandas, scikit-learn, Tableau, Excel**
**Dataset: UCI Default of Credit Card Clients dataset — 30,000 anonymized credit card customer records**

## Why I Built This Project

I built this project to understand how credit-risk analytics turns raw borrower data into actual portfolio decisions. Predicting whether a customer may default is only one part of the problem. In a lending environment, the more important question is what a bank does with that prediction: approve the customer, monitor the account more closely, adjust policy, flag the borrower for review, or accept the risk because the relationship may still be profitable.

That is why I structured this project as a full credit-risk workflow instead of a standalone machine learning model. I started with SQL-based portfolio analysis to identify where default risk, exposure, expected loss, and risk-adjusted profitability were concentrated. Then I built a Python modeling pipeline to score customers by predicted default risk, validated the model through lift and decile analysis, and translated the results into policy simulations and an executive Tableau dashboard.

The goal was to make the analysis feel closer to how a credit-risk, portfolio strategy, or banking analytics team would think. A high ROC-AUC score is useful, but it does not answer whether a lender should change its approval strategy. This project connects model performance to business outcomes by showing how predicted risk affects expected loss, approval rate, flagged customers, default capture, and simulated risk-adjusted profit.

## Business Question

Which borrower segments create the highest default risk, expected loss, risk-adjusted profitability, and portfolio exposure, and how can a lender use those insights to adjust approval, monitoring, and portfolio strategy?

## Project Overview

This project converts a 30,000-customer credit card default dataset into a credit-risk portfolio analytics system focused on loss concentration, borrower ranking, policy tradeoffs, and executive decision support. I designed the workflow to reflect how a lending analytics team would move from raw account-level data to portfolio strategy: first establishing a clean borrower-level dataset, then using SQL to profile risk, exposure, utilization behavior, expected loss, and risk-adjusted profitability across the portfolio before introducing any predictive model.

After the portfolio baseline was established, I simulated conservative, balanced, and growth-oriented credit policy strategies to test how different approval and monitoring rules would change customer volume, flagged accounts, default concentration, and profit-risk tradeoffs. This was a deliberate choice. In credit risk, a probability score has limited value unless it can be translated into an operational decision: whom to approve, whom to monitor, where expected loss is accumulating, and whether a policy improves the portfolio or simply shifts risk into another segment.

The modeling layer compares logistic regression, random forest, and histogram gradient boosting to estimate borrower default risk. The strongest model achieved a 0.779 ROC-AUC and produced meaningful separation across risk tiers, with the highest-risk decile showing a 75.03% observed default rate compared with a 22.12% portfolio default rate. Rather than treating accuracy as the final result, I evaluated the model through PR-AUC, precision, recall, risk-decile lift, threshold tradeoffs, and cumulative default capture so the output could be judged by its usefulness for review prioritization and portfolio monitoring.

The final Tableau dashboard connects the technical pipeline to lender decision-making. It shows where portfolio risk is concentrated, how quickly model-ranked review captures defaults and losses, how simulated policies trade off approval volume against risk-adjusted profitability, and which borrower groups create the largest expected-loss exposure. The project is intentionally framed as a portfolio analytics and decision-support system, not a production underwriting model, because the public dataset does not include the pricing, recovery, charge-off, and regulatory inputs required for real credit approval decisions.

## Tableau Dashboard

I created an executive Tableau dashboard to summarize portfolio risk, model performance, expected loss concentration, and credit policy strategy.

View the interactive dashboard here: https://public.tableau.com/views/PROJECT1_17820986935880/Dashboard1?:language=en-GB&publish=yes&:sid=&:redirect=auth&:display_count=n&:origin=viz_share_link

The dashboard includes:

* Executive KPI cards for portfolio size, observed default rate, predicted expected loss, and risk-adjusted profitability
* Default rate by predicted risk decile to show model risk separation
* A model gains curve comparing default and loss capture against a random review baseline
* A credit policy efficient frontier comparing approval rate, risk-adjusted profit, approved customer volume, and observed default risk
* An expected loss strategy matrix showing where portfolio loss is concentrated across risk deciles and credit strategies

The dashboard translates the Python, SQL, and machine learning outputs into an executive risk-management view that supports portfolio monitoring, policy comparison, and credit strategy decisions.

## Key Results

* Cleaned and structured 30,000 customer records into an analysis-ready dataset with 45 customer-level fields.
* Built SQL portfolio analysis for default rate, exposure, expected loss, revenue proxy, and risk-adjusted profitability.
* Simulated conservative, balanced, and growth-oriented credit policy strategies.
* Trained and compared logistic regression, random forest, and histogram gradient boosting models.
* Best model: Histogram Gradient Boosting
* Holdout test ROC-AUC: 0.779
* Holdout test PR-AUC: 0.557
* Holdout test accuracy: 81.78%
* Highest-risk holdout test decile showed a 3.15x default lift versus the portfolio average.
* Full-portfolio validation showed a top-risk decile default rate of 75.03% versus a portfolio default rate of 22.12%.
* Recommended model threshold: 0.150
* At the recommended threshold, the approved group had a 6.02% observed default rate, while the flagged group captured 86.38% of historical defaults.

## Project Workflow

| Step | Script | Purpose |
|---:|---|---|
| 1 | `notebooks/00_clean_raw_data.py` | Clean raw data, validate schema, and create business features |
| 2 | `notebooks/01_sql_portfolio_analysis.py` | Analyze segment risk, exposure, expected loss, and profitability |
| 3 | `notebooks/02_sql_credit_policy_simulation.py` | Simulate conservative, balanced, and growth-oriented policy strategies |
| 4 | `notebooks/03_credit_risk_model.py` | Train and compare default prediction models |
| 5 | `notebooks/04_model_validation_governance.py` | Validate calibration, thresholds, segment monitoring, fairness monitoring, and governance |

## Model Performance

| Metric | Value |
|---|---:|
| ROC-AUC | 0.779 |
| PR-AUC | 0.557 |
| Accuracy | 81.78% |
| Precision | 65.98% |
| Recall | 36.40% |
| Top holdout risk decile lift | 3.15x |

Top model drivers from permutation importance included maximum repayment delay, recent repayment status, utilization proxy, recent bill amount, credit limit, average payment amount, and average bill amount.

## Validation and Governance

| Metric | Value |
|---|---:|
| Portfolio observed default rate | 22.12% |
| Average predicted default probability | 22.12% |
| Calibration gap | 0.0042% |
| Brier score | 0.1223 |
| Top-risk decile default rate | 75.03% |
| Bottom-risk decile default rate | 1.63% |
| Top-risk decile lift | 3.39x |

### Recommended Threshold

| Metric | Value |
|---|---:|
| Recommended threshold | 0.150 |
| Approval rate | 50.06% |
| Flag rate | 49.94% |
| Approved observed default rate | 6.02% |
| Flagged observed default rate | 38.26% |
| Historical defaults captured by flagged group | 86.38% |
| Approved predicted risk-adjusted profit proxy | $33.36M |

## Design Decisions

I designed the project in stages because I wanted the analysis to follow the way a credit-risk team would actually think through a portfolio problem. Before building a model, I needed to understand the portfolio itself: where defaults were showing up, which customer groups carried the most exposure, and whether certain segments looked risky but still potentially profitable.

I used SQL as the first analytical layer because the early questions were portfolio questions, not machine learning questions. I wanted to profile default rate, utilization behavior, credit exposure, expected loss, revenue proxy, and risk-adjusted profitability across the customer base before introducing a prediction model. That made the modeling step more grounded because the business problem was already clear.

I added the policy simulation layer because a credit score only matters if it changes a decision. A lender does not use a model just to label someone risky; the score has to support choices around approval, monitoring, review, and portfolio strategy. By comparing conservative, balanced, and growth-oriented policies, I could see how different rules affected approved customers, flagged accounts, default concentration, and simulated risk-adjusted profit.

For modeling, I compared logistic regression, random forest, and histogram gradient boosting instead of presenting one model as if it were automatically the answer. Logistic regression gave me a simple benchmark, random forest added a nonlinear tree-based comparison, and histogram gradient boosting produced the strongest ranking performance based on ROC-AUC, PR-AUC, and risk-decile lift.

I focused on risk deciles, lift, threshold tradeoffs, and cumulative default capture because credit-risk models are often most valuable as ranking systems. Accuracy alone would not tell me whether the model could identify the riskiest borrowers early enough to support review or monitoring. The decile and gains-curve analysis made the model output much easier to connect to business action.

I treated the 0.150 threshold as a portfolio monitoring threshold, not a real underwriting cutoff. That distinction matters. In this project, the threshold shows how a lender could reduce approved-group default risk while capturing a large share of historical defaults in the flagged population. It is useful for decision support, but it is not a production approval rule.

## Assumptions and Limitations

I treated this project as a credit-risk analytics and decision-support exercise, not as a production underwriting system. The dataset is public and anonymized, which makes it useful for portfolio modeling, but it does not include several fields that a real bank would need before making actual lending decisions. Important variables such as APR, interest income, recovery rates, charge-off amounts, customer acquisition cost, credit bureau attributes, macroeconomic conditions, loss given default, exposure at default, and true account-level profitability are not available.

Because those fields are missing, I modeled expected loss, revenue, and risk-adjusted profitability using transparent proxy assumptions. I included those metrics because they make the analysis more realistic than looking at default probability alone, but I kept the interpretation limited. The profitability outputs are best understood as relative strategy comparisons, not actual bank earnings or production credit pricing.

The policy simulation is also historical and rule-based. It shows how conservative, balanced, and growth-oriented strategies would have performed on the available data, but it does not prove that the same results would hold in a future portfolio. In a real credit environment, policy changes would need out-of-time validation, portfolio monitoring, compliance review, and business approval before being used for customer decisions.

I also kept demographic variables separate from direct approval logic. In this project, they are used only for monitoring and fairness review, not for pricing, rejection, credit-line assignment, or final approval decisions. A production model would require much deeper governance, including adverse action reason codes, probability calibration, reject inference review, fairness testing, model documentation, challenger analysis, and model risk management approval.

## What I Would Improve Next

If I extended this project, I would make the validation closer to a production credit-risk workflow. The first improvement would be out-of-time validation, because a model that performs well on a random holdout sample still needs to prove that it can hold up across future booking periods and changing borrower behavior.

I would also add probability calibration, reject inference considerations, macroeconomic stress testing, and champion/challenger model comparison. Those additions would make the model easier to evaluate from both a business and model-risk perspective. For explainability, I would build adverse action reason-code logic and compare global feature importance with borrower-level explanations so that the model output could be translated into clearer credit decisions.

The biggest improvement would be a stronger profitability framework. If true banking fields were available, I would replace the proxy assumptions with actual APR, interest revenue, exposure at default, loss given default, recovery, charge-off, cost, and credit-line data. That would allow the project to move from relative policy simulation toward a more realistic portfolio profitability and credit strategy analysis.

## How to Run the Project
``` 
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python notebooks/00_clean_raw_data.py
python notebooks/01_sql_portfolio_analysis.py
python notebooks/02_sql_credit_policy_simulation.py
python notebooks/03_credit_risk_model.py
python notebooks/04_model_validation_governance.py 
```
## Resume Summary

Built an end-to-end credit risk analytics project using Python, SQL, DuckDB, scikit-learn, and Tableau to analyze 30,000 anonymized credit card customers across default risk, expected loss, exposure, and risk-adjusted profitability. Developed SQL portfolio analysis, credit policy simulations, borrower-level default models, validation outputs, governance monitoring, and an executive Tableau dashboard. Compared logistic regression, random forest, and histogram gradient boosting models, with the best model achieving 0.779 ROC-AUC and 3.15x top-decile lift on a holdout test set. Translated predicted default probabilities into risk deciles, threshold strategy, expected loss concentration, and simulated credit policy recommendations for portfolio decision support.