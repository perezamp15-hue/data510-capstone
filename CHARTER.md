# Studio Charter: GM Simulator 

> Filled in live during the **Studio Charter** session in week 3. Every section below is committed in the same commit at the end of that class block. See [Studio Charter (single-session inception)](https://courses.lpcordova.phd/data510/project-framework/charter-inception.html) for the script and time-boxes.

**Owner team:** Aaron Perez
**Owner Product Lead:** Aaron Perez
**Peer Stakeholder POs:** Bradley Allen,	Addison Gage,	Sarah Alhusaynat
**Instructor / Sponsor:** Lucas Cordova (`LucasCordova` on GitHub)
**GitHub repo:** [https://github.com/users/perezamp15-hue/projects/1/views/1](https://github.com/perezamp15-hue/data510-FitnessPal
**GitHub Projects board:** (https://github.com/perezamp15-hue/data510-FitnessPal)
**Discord category:** `#<project>-1`
**Studio Session:** 1
**Studio formed:** 5/25/2026

## Vision

The overarching vision of this initiative is to equip baseball organizations with a sophisticated predictive analytical environment, effectively translating raw environmental variables and individual player metrics into actionable intelligence to optimize strategic roster management and field positioning. 

## Mission
The primary mission of this project is to build a comprehensive data pipeline and data storage infrastructure, to create a simulation engine. By synthesizing official MLB statistical datasets with climate forecasts and unique stadium spatial parameters, the initiative aims to provide probabilistic game outcome distributions. Through a dynamic web based dashboard designed for general managers, offering comparative simulation capabilities between opposing teams.

## Context

- **Users / affected parties:** GM, and Front Office of baseball teams 
- **Data sources (proposed):** 
- **Constraints:** One of the main contraints is the ability to understand the player outcome on player psycological state
- **Ethics risks:** Predictive tools used by front offices directly impact player compensation, arbitration values, and field time. If a prediction model operates as an opaque "black box," it can create unfair biases against certain player profiles. To ensure transparency, the dashboard surfaces global feature importance metrics and local decision paths. This allows users to see exactly how much an environmental adjustment (e.g., wind speed) influenced a player's projected performance. 
Furthermore, the model limits inputs to on-field metrics, remaining blind to player age, contract size, or demographic backgrounds to maintain objective, performance-based predictions.


## Success criteria by milestone

- **M1, proposal (W4):** Finished hypothesis and goal
- **M2, data summary (W7):** data sources are collected and organize
- **M3, poster rough draft (W10):** Finished mocked up of the poster and organzation
- **M4, write-up rough draft (W12):** At least 70% of the paper done
- **M5, final write-up and poster (W14):** Everything is finished

## Working agreements (internal to owner team)

- **Sync rhythm:** Solo Project`#<project>-standup`
- **Code review:** Solo Project
- **Decision rule:** Solo Project

## Working agreements (triad with peer POs)

- **Studio Brief due:** Should the Brief be needed will need to be done on major milestone or requested should be sumbited to`studio/briefs/W<NN>-<peer>.md` and linked in `#<project>-studio` on Discord. If the owner team needs the peer POs to read or review something specific *before* the Studio Session (a data preview, model results, a draft figure), 
- **Studio Critique due:** The Studio Criquite will be due in studio/criqute/ when major milestones are due and as needed by the owner.
- **Priority conflict resolution:** owner team integrates briefs in good faith; the instructor arbitrates (as Process Expert) if peer POs and owner team disagree.

## Response SLAs (Service Level Agreements)

A **Service Level Agreement** is a written promise the triad makes about *how fast* each side responds when a specific signal arrives. Every row must have an answer before this Charter is committed. See [Response SLAs](https://courses.lpcordova.phd/data510/project-framework/charter-inception.html#response-slas-service-level-agreements) for the full definition.

| When this signal arrives... | Who responds | By when |
|-----------------------------|--------------|---------|
| Peer PO files a **Studio Brief** (commits to `studio/briefs/...`, links in `#<project>-studio`) | Owner team | <e.g., acknowledge in `#<project>-studio` within 24 hours, with a first-pass adopt / defer / decline call for each item> |
| Peer PO files a **Studio Critique** | Owner team | <e.g., respond in `#<project>-studio` within 24 hours and capture follow-up items into the backlog> |
| Owner team posts an **Iteration Review** in `README.md` | Both peer POs | <e.g., read before filing the next Brief and Critique> |
| Owner team flags a **blocker** in `#<project>-blockers` | Instructor, plus any tagged peer PO | <e.g., responds by the next Studio Session at the latest; faster if online> |
| Anyone asks a clarifying question in `#<project>-general` | Whoever is tagged (default: owner team) | <e.g., reply within 48 hours, even if the reply is "we will look at this next iteration"> |

## Definition of Ready (PBI)

A PBI is ready to be pulled out of `Backlog` and moved into `Create` when it has:

- A one-sentence hypothesis or user story.
- A named **Create**, **Observe**, **Analyze** triple.
- A milestone tag (`M1-proposal`, `M2-data-summary`, `M3-poster-draft`, `M4-writeup-draft`, `M5-final`, `infra`, `ethics`).
- A T-shirt size estimate (S, M, L, XL).
- WIP slack on the board: `Create + Observe + Analyze` is below the team's WIP cap (owners + 1).

## Definition of Done (PBI)

A PBI is done, and may be moved from `Analyze` into `Done`, when:

- The Create artifact is in the repo or linked from the issue.
- The Observe results are recorded somewhere referenceable (notebook output, processed dataset, draft results section).
- The Analyze writeup names a next step (continue, pivot, kill, or decompose into new PBIs).
- A peer PO has either signed off in `#<project>-studio` or filed a Studio Critique covering it.
- The card is linked under *Completed PBIs* in the next Iteration Review in `README.md`.

## Stakeholder alignment memo (one-page summary)

### Why we exist
If successful, this project demonstrates a reproducible blueprint for contextual sports analytics. Organizations benefit from a sports-analytics framework capable of running "what-if" environmental simulations allowing front offices to optimize starting lineups, pitching rotations, and in-game strategic shifts based on real-time weather changes and park dimensions. 

### What we will deliver to peer POs every week
- An Iteration Review in this `README.md` by Sunday/ by 11:59pm
- A summary of which Studio Brief items we adopted, deferred, or declined and why

### What we need from peer POs every week
- A Studio Brief by if there is a studion Brief is needed for the week than it is due before class
- A Studio Critique by if they 

### How to reach us
- Discord category: `#<project>-general` (day-to-day), `#<project>-studio` (Briefs and Critiques), `#<project>-blockers` (impediments)
- GitHub repo: https://github.com/perezamp15-hue/data510-FitnessPal
- GitHub Projects board: https://github.com/users/perezamp15-hue/projects/1/views/1
