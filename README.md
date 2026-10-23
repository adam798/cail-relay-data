# Ouroboros: AI Operations Assistant for Mission-Critical Systems

**Catalyst 2026 · Case Study Challenge #5 (sponsor: CAIL Systems Inc.) · Team #24**
Adan Abdullahi · Rong Hao · Dhruva Rau

**Live demo:** https://ouroboros-mission-control.lovable.app
**Team repository (web app):** https://github.com/dhruvarau/Ouroboros

## The problem
Banks, card networks, and payment systems run on HPE NonStop servers, where downtime is not an option. Monitoring tools detect problems, but understanding them and choosing the next safe step still depends on a small number of senior experts.

## What Ouroboros does
- **Monitor:** shows system health, alerts, and incidents in one place
- **Explain:** lets operators ask troubleshooting questions in plain English
- **Guide safely:** suggests commands from an approved catalog with a risk label (SAFE, CAUTION, HIGH RISK) and requires operator approval or senior escalation
- **Preserve knowledge:** captures expert troubleshooting guidance, reviewed by a second senior
- **Audit:** records every action

## Try the demo
1. Open **System Overview** to see system health and an active incident.
2. Ask the assistant a question such as "Why are transactions slow?"
3. Review the explanation, the evidence, and the suggested diagnostic command with its risk label.
4. Explore the approval and escalation steps for different risk levels.
5. Visit **Knowledge** to see how expert guidance is captured and reviewed, and **Audit** to see recorded activity.

The web app code (React, TypeScript, Tailwind CSS) is in the [team repository](https://github.com/dhruvarau/Ouroboros).

## This repository: data and anomaly detection
Real NonStop systems and bank data are confidential, so this repo simulates them:
- 24 hours of minute-level system metrics with 3 planted incidents (looping payment process, CPU hardware failure, disk filling)
- Alerts tagged with the monitoring tool that would raise them and a severity rank
- Unsupervised anomaly detection: rolling z-score, Isolation Forest (trained on a separate normal day), and a trend check
- A command catalog with risk labels and the AI system prompt

### Results (tested on an unseen day)
| Accuracy | Precision | Recall | F1 | Incidents caught |
|---|---|---|---|---|
| 98.7% | 95.8% | 92.9% | 0.94 | 3 of 3 |

The disk incident was detected **40 minutes before** the first alert.

## Repository structure
| Path | Purpose |
|---|---|
| `data-sim/simulate_nonstop.py` | Generates the data, runs detection, exports JSON |
| `data-sim/CAIL_Relay_Data_Analysis.ipynb` | Data quality checks, EDA, train/test split, evaluation |
| `data-sim/data/` | Metrics, alerts, incidents, anomalies, commands, users, knowledge, system prompt |
| `pitch/` | Analysis summary and chart used in the pitch |

## Run
```bash
cd data-sim
pip install numpy pandas scikit-learn matplotlib
python3 simulate_nonstop.py
```

## Tech
Python, pandas, NumPy, scikit-learn (Isolation Forest), Matplotlib. Web app: React, TypeScript, Tailwind CSS.

*Note: Ouroboros is a demonstration built on simulated data, not a production integration.*
