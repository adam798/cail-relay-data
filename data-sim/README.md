# CAIL Relay: Data + Anomaly Detection

**Catalyst 2026 · Case Study Challenge #5 (sponsor: CAIL Systems Inc.) · Team #24**
Adan Abdullahi · Rong Hao · Dhruva Rau

> *How might we use AI to help the next generation of IT operators understand, monitor, and troubleshoot mission-critical enterprise systems through natural language, while preserving the expertise of experienced professionals?*

## What this is
The data layer behind **CAIL Relay**, an AI assistant inside CAIL's terminal for HPE NonStop. Banks' monitoring tools (ASAP, Prognosis, ViewSys) detect problems; CAIL Relay explains them, suggests the next safe command with a risk label, waits for human approval, and preserves expert knowledge.

We cannot access real NonStop systems or those tools, so this repo **simulates** them:
- 24h of minute-level NonStop metrics with **3 planted incidents** (looping payment process, CPU hardware failure, disk filling)
- Alerts tagged with the **monitoring tool** that would raise them and a **severity rank**
- **Unsupervised anomaly detection**: rolling z-score + Isolation Forest (trained on a separate normal day) + trend check
- A **command catalog** the AI may suggest from, with SAFE / CAUTION / HIGH RISK labels
- The **AI system prompt**

## Results (tested on an unseen day)
| Accuracy | Precision | Recall | F1 | Incidents caught | Operator alerts |
|---|---|---|---|---|---|
| 98.7% | 95.8% | 92.9% | 0.94 | 3 / 3 | 3, all real |

Disk incident detected **40 minutes before** the first alert.

## Run
```bash
pip install numpy pandas scikit-learn matplotlib
python3 simulate_nonstop.py
```
Full analysis: `CAIL_Relay_Data_Analysis.ipynb` (Jupyter: Run > Run All Cells).

## Files
| File | Purpose |
|---|---|
| `simulate_nonstop.py` | Generates all data, runs detection, exports JSON |
| `CAIL_Relay_Data_Analysis.ipynb` | Quality checks, EDA, train/test, evaluation |
| `data/metrics.json` | 1,440 minutes of metrics + anomaly flags |
| `data/events.json` | Alerts with source tool and severity rank |
| `data/incidents.json` | The 3 incidents (ground truth) |
| `data/anomalies.json` | Detected anomaly windows |
| `data/commands.json` | Commands the AI may suggest, with risk + source + output |
| `data/users.json` | Simulated users, roles (junior, senior, manager) and permission rules |
| `data/knowledge.json` | Runbooks + senior notes with two-person review status (approved / pending / rejected) |
| `data/summary.json` | Run summary |
| `data/system_prompt.md` | Instructions for the AI assistant |
| `data/chart.png` | 24h chart with detected anomalies |

## Assumptions and limits
All data is simulated. Names follow NonStop conventions; command syntax is illustrative and must be verified against HPE manuals. Thresholds would need tuning on real data.
