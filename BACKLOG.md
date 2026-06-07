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

## Items

### PBI-001: Initial Data Acquisition

- **Title:** Acquire and document initial MLB and weather data feeds
- **Hypothesis:** Historical MLB player metrics, stadium layouts, and hourly Open-Meteo weather parameters are programmatically accessible, license-compatible, and possess sufficient data density to evaluate short-term environmental impacts.
- **Create:** Ingestion script and `data/README.md` section describing schema.
- **Observe:** Row counts, missingness, key uniqueness, distribution sanity checks.
- **Analyze:** Decide whether the dataset survives feasibility; document in the next Iteration Review.
- **Tag:** `M2-datasummary`, `infra`
- **Size:** M
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-002: Cloud Infrastructure Setup
- **Title:** Establish Cloud DB Infrastructure and Connect Management GUI
- **Hypothesis:** Setting up an online cloud relational database with local GUI management allows for fast, multi-table structural querying and eliminates local file locking issues.
- **Create:** Live PostgreSQL instance on Railway and configure a secure, SSL-encrypted connection inside Beekeeper Studio.
- **Observe:** Connection uptime checks, test table creations via Beekeeper, and environment variable verifications.
- **Analyze:** Confirm that the cloud infrastructure performance is stable enough to serve as our central data warehouse repository.
- **Tag:** `M2-datasummary`, `infra`
- **Size:** S
- **GitHub issue:** *Leave blank for GitHub integration*


---

### PBI-003: Ingestion Pipeline Engineering
- **Title:** Build Data Ingestion Pipeline to Automate Local File Tiering
- **Hypothesis:** Programmatically separating data into raw, interim, and processed directories protects raw data files from corruption and lets us perfectly reproduce our steps.
- **Create:** File transfer logic inside `src/ingest.py` that downloads raw API payloads into `data/raw/` and merges them cleanly into `data/interim/` based on game timestamps.
- **Observe:** Pipeline execution runtime logs, API network timeout catches, and local directory folder verifications.
- **Analyze:** Verify that data flows flawlessly through the local directory structure without breaking data types or changing the original metrics.
- **Tag:** `M2-data-summary`
- **Size:** L
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-004: Data Cleaning & Summary Report

- **Title:** Construct Exploratory Data Summary and Check Missingness
- **Hypothesis:** A systematic review of missing values, anomalies, and structural distribution plots will expose hidden data gaps before we begin training models.
- **Create:** Data evaluation notebook in `notebooks/` and compile the formal `M2-data-summary` report inside the `deliverables/` folder.
- **Observe:** Check and plot outliers (extreme weather spikes, broken player IDs) and calculate missing row distributions.
- **Analyze:** Create explicit data-cleaning and row-dropping rules to guarantee our data is completely clean before model training.
- **Tag:** `M2-data-summary`
- **Size:** M
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-005: Modeling Benchmarks

- **Title:** Implement Baseline Performance Models and Benchmarks
- **Hypothesis:** Building basic season-long aggregate models establishes a clear predictive accuracy ceiling that we must beat to prove weather features are valuable.
- **Create:** Basic baseline Logistic Regression model (for wins) and a Linear Regression model (for runs scored) using only season-aggregate metrics.
- **Observe:** Testing set baseline metrics including macro-F1 score and run prediction Mean Absolute Error (MAE).
- **Analyze:** Identify exactly where traditional models fail due to ignoring weather and park sizes, establishing our target benchmark metrics.
- **Tag:** `M2-data-summary`
- **Size:** M
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-006: Advanced Feature Engineering
- **Title:** Engineer Rolling Features and Environmental Wind Vectors
- **Hypothesis:** Breaking wind angles into directional vectors and computing 15-game rolling averages provides the model with the exact situational context needed to predict at-bats.
- **Create:** Feature calculation code inside `src/features.py` to compute rolling player form metrics, trigonometry-based wind vectors ($X$ and $Y$ dimensions), and local air density values.
- **Observe:** Look over the newly generated feature matrices inside `data/processed/` and confirm all text values successfully transformed into numbers.
- **Analyze:** Inspect feature correlation matrices to check for multi-collinearity issues and ensure no future data leakage across the $t-1$ boundary.
- **Tag:** `M3-poster-draft`
- **Size:** L
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-007: XGBoost Classification
- **Title:** Train and Optimize Multi-Class XGBoost At-Bat Classifier
- **Hypothesis:** A gradient-boosted decision tree can successfully predict discrete plate-appearance probability distributions when fed short-term form and environmental features.
- **Create:** XGBoost Multi-Class Classifier mapping features to categorical 
- **Observe:** Multi-class Log Loss metrics, Macro-F1 scores against the testing split, and feature importance ranking charts.
- **Analyze:** Assess whether adding wind and air density columns statistically reduced model log loss compared to models built on player data alone.
- **Tag:** `M3-poster-draft`
- **Size:** L
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-008: Monte Carlo Engine Setup
- **Title:** Program the Monte Carlo Simulation Engine State Machine
- **Hypothesis:** Simulating a game plate-appearance by plate-appearance 10,000 times creates a realistic distribution of score outcomes that outperforms flat game-level guesses.
- **Create:** Full baseball game state machine loop inside `src/simulator.py` to track innings, outs, base runners, and batting order rotations.
- **Observe:** batch simulation loops for validation games, recording the resulting run distributions, projected final scores, and win percentages.
- **Analyze:** Compare the simulator's score prediction Mean Absolute Error (MAE) against baseline models to determine if our contextual simulator beats traditional methods 
- **Tag:** `M3-poster-draft`
- **Size:** XL
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-009: Model Ethics & Audit
- **Title:** Audit Model Transparency and Map Strategic Interpretability
- **Hypothesis:** Surfacing the exact feature weights behind each matchup simulation prevents black-box confusion and protects against unfair player performance evaluations.
- **Create:** Algorithmic explanation section inside `deliverables/` and embedded feature importance visualizers inside the model tracking script.
- **Observe:** Sample simulation prediction paths to confirm the model changes outputs based purely on performance math, remaining blind to player demographics.
- **Analyze:** Evaluate if our metrics remain fair and explainable under extreme scenario tests; present these ethical boundaries to peer POs during Studio Critique.
- **Tag:** `M4-writeup-draft`, `ethics`
- **Size:** S
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-010: Mid-Term Reporting Deliverables
- **Title:** Assemble Technical Poster and Draft Capstone Writeup
- **Hypothesis:** Displaying our methodology via visual system-lineage diagrams and clean metric tables effectively translates complex data logic into clear insights for non-technical stakeholders.
- **Create:** Visual technical poster layout (`M3-poster-draft`) and write the formal capstone project manuscript draft (`M4-writeup-draft`).
- **Observe:** Feedback metrics from peer Studio Critiques regarding text readability, diagram clarity, and model explanations.
- **Analyze:** Refine descriptions of our machine learning models and system architecture to meet all grading standards before final submission.
- **Tag:** `M4-writeup-draft`
- **Size:** L
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-011: User Interface Design
- **Title:** Develop Interactive UI Frontend with Simulation Controls
- **Hypothesis:** Giving users interactive roster dropdown menus and weather override sliders allows General Managers to easily conduct real-time "what-if" strategic simulations.
- **Create:** Web-based frontend dashboard app using Streamlit that accepts lineup selections and environmental variables.
- **Observe:** Manual user testing logs checking for UI layout bugs, interface lag, and instant recalculation verification.
- **Analyze:** Review user workflows to ensure the dashboard interface prioritizes clean probability visualizations over dense text numbers.
- **Tag:** `M5-final`
- **Size:** L
- **GitHub issue:** *Leave blank for GitHub integration*

</details>

---

### PBI-012: Production Deployment Tasks
- **Title:** Connect FastAPI Backend and Deploy Live Web App to Railway
- **Hypothesis:** Wrapping our simulation logic inside a FastAPI backend and hosting it on Railway allows users to securely access our application from any web browser.
- **Create:** Production API endpoint routes inside `src/app.py`, clean environment configuration files, and live web application hosting on Railway.
- **Observe:** Cloud deployment build logs, server boot status, API endpoint response times, and public URL availability.
- **Analyze:** Audit the live application to confirm database connection pools and model inferences function properly under continuous cloud web hosting conditions.
- **Tag:** `M5-final`, `infra`
- **Size:** M
- **GitHub issue:** *Leave blank for GitHub integration*

</details>
