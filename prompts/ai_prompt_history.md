# AI Prompt History and Usage Disclosure

## 1. AI tool disclosure

ChatGPT (OpenAI) was used as an AI assistance tool during development of the **YottaFlex Customer Churn and Retention Experiment Pipeline**.

AI assistance supported project planning, requirement interpretation, data-model design, Python implementation guidance, business-rule development, validation, testing, debugging, and documentation.

The project code was executed locally. Suggested changes were reviewed and tested before being incorporated into the project.

## 2. AI tool information

| Item | Details |
|---|---|
| AI tool | ChatGPT |
| Provider | OpenAI |
| Project | YottaFlex Customer Churn and Retention Experiment Pipeline |
| Development period | October 2026 |
| Areas of assistance | Planning, implementation guidance, debugging, testing guidance, code review, and documentation |
| Code execution | Performed locally using Python |

## 3. Record of prompts and requests

The following table records the main requests made to ChatGPT during development. These are concise summaries of the requests, not verbatim quotations or a complete message-by-message transcript.

| No. | Date | Prompt / request summary | Purpose |
|---:|---|---|---|
| 1 | October 2026 | Help me understand and implement the YottaFlex churn and retention experiment problem statement as a separate project. | Requirement analysis and project planning |
| 2 | October 2026 | Design a reproducible synthetic customer dataset with 20,000 customers and 18 months of historical records using a fixed random seed. | Synthetic data generation |
| 3 | October 2026 | Implement the customer, subscription, usage snapshot, billing event, support case, offer, eligibility rule, campaign contact, churn outcome, and retention outcome entities. | Data model and entity relationships |
| 4 | October 2026 | Implement offer eligibility using churn risk, active subscription status, offer cooldown, monthly contribution margin, and maximum offer cost. | Eligibility rules |
| 5 | October 2026 | Generate churn-risk features from historical usage, failed payments, and support cases, without using information after the prediction date. | Feature engineering and temporal leakage prevention |
| 6 | October 2026 | Implement treatment/control assignment and simulate churn and retention outcomes using documented assumptions. | Experiment simulation |
| 7 | October 2026 | Inject and label the four required anomalies: churn before prediction, offer to an ineligible customer, treatment/control leakage, and multiple offer attribution. | Anomaly generation |
| 8 | October 2026 | Implement validation for primary keys, foreign keys, dates, eligibility, experiment assignment, and intentional anomalies. | Data validation |
| 9 | October 2026 | Export generated data to CSV, JSON, SQLite, and standalone SQL schema and seed-data files. | Data export and database implementation |
| 10 | October 2026 | Add a feature snapshot export and include it in reproducibility verification. | Feature export and reproducibility |
| 11 | October 2026 | Help debug implementation issues and provide complete updated Python files when changes are required. | Debugging and code maintenance |
| 12 | October 2026 | Verify full-scale generation, unit tests, database integrity, SQL exports, and fixed-seed reproducibility. | Testing and quality assurance |
| 13 | October 2026 | Diagnose unexpected validation errors in generated churn and retention data; inspect the validator and correct Boolean handling without regenerating the dataset. | Validation debugging |
| 14 | October 2026 | Add subscription-history records and ensure the entity is included in validation and database exports. | Data-model extension |
| 15 | October 2026 | Review the CLI and storage implementation for consistency with the eleven-entity data model and correct standalone validation table handling. | CLI and export integration |
| 16 | October 2026 | Review project requirements and identify remaining implementation, documentation, testing, and submission gaps. | Requirements and submission review |
| 17 | October 2026 | Review the README, assumptions, data dictionary, and AI-use disclosure for the final submission. | Documentation |
| 18 | October 2026 | Review and update the AI prompt-history disclosure to cover development, debugging, integration, and documentation assistance. | AI-use disclosure |

## 4. Candidate review and verification

ChatGPT suggestions were used as assistance and were not treated as automatically correct. The implementation was run locally and reviewed through tests and generated outputs.

The following results were recorded during development:

| Verification activity | Recorded result |
|---|---|
| Full-scale synthetic generation | 20,000 customers generated |
| Historical usage records | 360,000 snapshots generated |
| Feature snapshot | 20,000 feature rows exported |
| Latest reported unit-test run | 16 tests passed |
| SQLite integrity check on the supplied project database | `ok` |
| SQLite foreign-key check on the supplied project database | 0 violations |
| Reproducibility verification | The included report records identical CSV hashes for the same-seed run |
| Intentional anomaly validation | Four expected anomaly types reported |

The validation report is expected to report the four deliberately injected anomalies. Therefore, a validation status of `passed: false` is intentional when those anomalies are present; it should not be represented as a clean validation pass.

## 5. Review decisions and implementation changes

During development, the following implementation and review decisions were made:

- Kept the churn-risk calculation as an explainable heuristic rather than describing it as a trained machine-learning model.
- Ensured that feature calculations use pre-prediction records.
- Kept ground-truth anomaly metadata separate from analytical features.
- Preserved the four intentional anomalies so that the validation process could detect and report them.
- Added subscription-history support and included it in the data model and validation/export workflow.
- Corrected Boolean handling in validation so that CSV text values such as `False` are not incorrectly treated as truthy values.
- Added eligibility traceability and offer-response information to support validation and experiment-cost calculations.
- Updated metrics logic so realized offer cost is attributed according to the simulated response and attribution rules.
- Documented that synthetic experiment results are illustrative and do not demonstrate real-world causal effectiveness.

## 6. Responsible use and ownership

AI assistance does not replace the candidate's responsibility for the submitted work. The implementation was run locally and reviewed through tests and generated outputs. The candidate is responsible for understanding the submitted code, results, dependencies, assumptions, and limitations.

The candidate should be able to explain:

- The purpose of each project module.
- The data model and entity relationships.
- The churn-risk feature calculations.
- The offer eligibility and margin constraints.
- The treatment/control assignment process.
- The four injected anomalies and their validation logic.
- The experiment metrics and their limitations.
- The database schema, exports, and reproducibility checks.

## 7. Scope and accuracy of this record

This file is a development-history summary of the main ChatGPT requests and assistance areas. It is **not a verbatim export of every ChatGPT message** and does not claim to be a complete message-by-message transcript. Dates are shown at month level because exact timestamps for each request have not been independently recorded.

ChatGPT is the AI tool recorded in this document. No other AI tool is listed here. This disclosure describes the known use of AI assistance and distinguishes request summaries from exact prompt quotations.
