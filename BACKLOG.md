# Backlog: <project name>

This file is the **human-readable mirror** of the [GitHub Projects (v2) Iterative Development board](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects) for this repo. Every row here is also a GitHub issue, added to the board, tagged with a milestone label, and sized.

## Conventions

- Each item has: id, title, hypothesis or user story, **Create / Observe / Analyze** triple, milestone tag, size.
- Items are ordered top to bottom by **priority**.
- Milestone tags: `M1-proposal`, `M2-data-summary`, `M3-poster-draft`, `M4-writeup-draft`, `M5-final`, `infra`, `ethics`.
- Sizes: S, M, L, XL.
- The board has five columns: `Backlog` → `Create` → `Observe` → `Analyze` → `Done`. Each column is the *phase of work happening on a single PBI right now*, not a work type. See the [Iterative Development board explainer](https://courses.lpcordova.phd/data510/project-framework/#github-projects-board-per-project-iterative-development-board) for what each column means and when to advance a card.
- WIP cap: `Create + Observe + Analyze` ≤ `owners + 1` at any time.
- Definition of Ready and Definition of Done live in [`CHARTER.md`](CHARTER.md).


PBI-001
ID: PBI-001
Title: Acquire and document initial MLB and weather data feeds
Hypothesis: Historical MLB player metrics, stadium layouts, and hourly Open-Meteo weather parameters are programmatically accessible, license-compatible, and possess sufficient data density to evaluate short-term environmental impacts.
Create: Write the initial pipeline extraction script (src/ingest.py) and a comprehensive schema dictionary inside the data/README.md file.
Observe: Log raw table row counts, calculate data missingness percentages, check structural primary/foreign key uniqueness, and perform initial distribution sanity checks.
Analyze: Decide whether the acquired dataset survives feasibility constraints to support the plate-appearance model; document findings in the next Iteration Review.
Tag: M1-proposal, infra
Size: M
GitHub Issue: [Leave blank for GitHub integration]
PBI-002
ID: PBI-002
Title: Draft research question and frame as a testable claim
Hypothesis: We can state the project's research question in a single, clear sentence that explicitly names the target population, the environmental predictors, and the performance outcomes.
Create: Write the finalized Research Question statement in the CHARTER.md Mission section and supply a detailed one-paragraph problem framing in the proposal draft.
Observe: Check if a peer PO who has never seen the project can read the statement and repeat the exact core claim back accurately without confusion.
Analyze: Revise and refine the wording boundaries based directly on Studio Brief and instructor feedback.
Tag: M1-proposal
Size: S
GitHub Issue: [Leave blank for GitHub integration]
PBI-003
ID: PBI-003
Title: Establish Cloud DB Infrastructure and Connect Management GUI
Hypothesis: Setting up an online cloud relational database with local GUI management allows for fast, multi-table structural querying and eliminates local file locking issues.
Create: Provision a live PostgreSQL database instance on Railway and configure a secure, SSL-encrypted connection inside Beekeeper Studio.
Observe: Execute connection uptime checks, run test table creations via Beekeeper, and verify that the database connection string strings work inside local test environment variables.
Analyze: Confirm that the cloud infrastructure performance is stable enough to serve as our central data warehouse repository.
Tag: M1-proposal, infra
Size: S
GitHub Issue: [Leave blank for GitHub integration]
PBI-004
ID: PBI-004
Title: Build Data Ingestion Pipeline to Automate Local File Tiering
Hypothesis: Programmatically separating data into raw, interim, and processed directories protects raw data files from corruption and lets us perfectly reproduce our steps.
Create: Write file transfer logic inside src/ingest.py that downloads raw API payloads into data/raw/ and merges them cleanly into data/interim/ based on game timestamps.
Observe: Monitor pipeline execution runtime logs, catch script API network timeout crashes, and check that files land in their correct folders without data loss.
Analyze: Verify that data flows flawlessly through the local directory structure without breaking the columns or changing the original source metrics.
Tag: M2-data-summary
Size: L
GitHub Issue: [Leave blank for GitHub integration]
PBI-005
ID: PBI-005
Title: Construct Exploratory Data Summary and Check Missingness
Hypothesis: A systematic review of missing values, anomalies, and structural distribution plots will expose hidden data gaps before we begin training models.
Create: Author a data evaluation document in notebooks/ and compile the formal M2-data-summary report inside the deliverables/ folder.
Observe: Check and plot outliers (e.g., extreme weather spikes or broken player IDs) and calculate exactly how missing rows are distributed across the 2-season dataset.
Analyze: Create explicit data-cleaning and row-dropping rules (e.g., handling rained-out games) to guarantee our data is completely clean before model training.
Tag: M2-data-summary
Size: M
GitHub Issue: [Leave blank for GitHub integration]
PBI-006
ID: PBI-006
Title: Implement Baseline Performance Models and Benchmarks
Hypothesis: Building basic season-long aggregate models establishes a clear predictive accuracy ceiling that we must beat to prove weather features are valuable.
Create: Build a basic baseline Logistic Regression model (for wins) and a Linear Regression model (for runs scored) in src/features.py using only season-aggregate metrics.
Observe: Compute and record the baseline performance metrics on the 2025 testing set: chart macro-F1 score and record score prediction Mean Absolute Error (MAE).
Analyze: Identify exactly where traditional models fail due to ignoring weather and park sizes, establishing our target benchmark metrics.
Tag: M2-data-summary
Size: M
GitHub Issue: [Leave blank for GitHub integration]
PBI-007
ID: PBI-007
Title: Engineer Rolling Features and Environmental Wind Vectors
Hypothesis: Breaking wind angles into directional vectors and computing 15-game rolling averages provides the model with the exact situational context needed to predict at-bats.
Create: Write feature calculation code inside src/features.py to compute rolling player form metrics, trigonometry-based wind vectors (X and Y dimensions), and local air density values.
Observe: Look over the newly generated feature matrices inside data/processed/ and confirm that all text values have been successfully transformed into numerical arrays.
Analyze: Inspect feature correlation matrices to check for multi-collinearity issues and ensure no future game data leaked into past rows.
Tag: M3-poster-draft
Size: L
GitHub Issue: [Leave blank for GitHub integration]
PBI-008
ID: PBI-008
Title: Train and Optimize Multi-Class XGBoost At-Bat Classifier
Hypothesis: A gradient-boosted decision tree can successfully predict discrete plate-appearance probability distributions when fed short-term form and environmental features.
Create: Train an XGBoost Multi-Class Classifier mapping features to categorical outcomes: [Single, Double, Triple, Home Run, Walk, Out].
Observe: Evaluate the multi-class Log Loss and Macro-F1 score against the testing split, and output feature importance ranking charts.
Analyze: Assess whether adding wind and air density columns statistically reduced model log loss compared to models built on player data alone.
Tag: M3-poster-draft
Size: L
GitHub Issue: [Leave blank for GitHub integration]
PBI-009
ID: PBI-009
Title: Program the Monte Carlo Simulation Engine State Machine
Hypothesis: Simulating a game plate-appearance by plate-appearance 10,000 times creates a realistic distribution of score outcomes that outperforms flat game-level guesses.
Create: Code the full baseball game state machine loop inside src/simulator.py to track innings, outs, base runners, and batting order rotations.
Observe: Execute 10,000 batch simulation loops for the validation games and record the aggregated team run totals and win percentages.
Analyze: Evaluate final macro accuracy. Compare the simulator's score prediction MAE against the PBI-006 baseline to determine if our contextual simulator beats traditional methods.
Tag: M3-poster-draft
Size: XL
GitHub Issue: [Leave blank for GitHub integration]
PBI-010
ID: PBI-010
Title: Audit Model Transparency and Map Strategic Interpretability
Hypothesis: Surfacing the exact feature weights behind each matchup simulation prevents black-box confusion and protects against unfair player performance evaluations.
Create: Write an algorithmic explanation section inside deliverables/ and embed clear feature importance visualizers directly into the model tracking script.
Observe: Trace sample simulation prediction paths to confirm the model changes outputs based purely on performance math, remaining blind to player demographics or contract size.
Analyze: Evaluate if our metrics remain fair and explainable under extreme scenario tests; present these ethical boundaries to peer POs during Studio Critique.
Tag: M4-writeup-draft, ethics
Size: S
GitHub Issue: [Leave blank for GitHub integration]
PBI-011
ID: PBI-011
Title: Assemble Technical Poster and Draft Capstone Writeup
Hypothesis: Displaying our methodology via visual system-lineage diagrams and clean metric tables effectively translates complex data logic into clear insights for non-technical stakeholders.
Create: Draft the visual technical poster layout (M3-poster-draft) and write the formal capstone project manuscript draft (M4-writeup-draft).
Observe: Gather feedback metrics from peer Studio Critiques regarding text readability, diagram clarity, and the explanation of our statistical methods.
Analyze: Refine the descriptions of our machine learning models and system architecture to meet all grading standards before the final submission deadline.
Tag: M4-writeup-draft
Size: L
GitHub Issue: [Leave blank for GitHub integration]
PBI-012
ID: PBI-012
Title: Develop Interactive UI Frontend with Simulation Controls
Hypothesis: Giving users interactive roster dropdown menus and weather override sliders allows General Managers to easily conduct real-time "what-if" strategic simulations.
Create: Build a functional, web-based frontend dashboard using Streamlit that accepts lineup selections and environmental variables.
Observe: Run manual user testing to check for UI layout bugs, interface lag, and verify that changing sliders instantly recalculates the simulation output.
Analyze: Review user workflows to ensure the dashboard prioritizes clean probability visualizations over dense, unorganized numbers.
Tag: M5-final
Size: L
GitHub Issue: [Leave blank for GitHub integration]
PBI-013
ID: PBI-013
Title: Connect FastAPI Backend and Deploy Live Web App to Railway
Hypothesis: Wrapping our simulation logic inside a FastAPI backend and hosting it on Railway allows users to securely access our application from any web browser.
Create: Build production API endpoint routes inside src/app.py, set up a clean requirements.txt file, and deploy the application live on Railway.
Observe: Monitor cloud deployment logs, catch server boot errors, check endpoint response times, and test public URL availability.
Analyze: Audit the live application to confirm that database connection pools and model inferences function properly under continuous web hosting conditions.
Tag: M5-final, infra
Size: M
GitHub Issue: [Leave blank for GitHub integration]
