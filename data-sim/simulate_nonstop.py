"""
CAIL Relay - simulated HPE NonStop system data (Catalyst 2026, Team #24)

Generates 24h of minute-level metrics, EMS-style events, 3 injected incidents,
simulated command outputs, and runs anomaly detection. Exports JSON for the app.

All data is SIMULATED and illustrative. Names follow real NonStop conventions
($PAY1, $DATA01, TMF, EMS) but are not from a real system.

Run:  python3 simulate_nonstop.py
Out:  data/metrics.json, data/events.json, data/incidents.json,
      data/anomalies.json, data/commands.json, data/users.json, data/knowledge.json, data/summary.json, data/chart.png
"""

import json
import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

SEED = 42
START = datetime(2026, 10, 17, 0, 0)
MINUTES = 24 * 60
OUT = "data"
NODE = "\\PROD1"

rng = np.random.default_rng(SEED)
os.makedirs(OUT, exist_ok=True)


def t(minute):
    return START + timedelta(minutes=minute)


def hhmm(h, m):
    return h * 60 + m


# ---------------------------------------------------------------------------
# 1. Incidents (ground truth). Times are minutes since midnight.
# ---------------------------------------------------------------------------
INCIDENTS = [
    {
        "id": "INC-001",
        "title": "Payment server $PAY1 looping on CPU 2",
        "start": hhmm(2, 14), "fix": hhmm(2, 24), "end": hhmm(2, 34),
        "severity": "HIGH",
        "symptoms": "CPU 2 at ~96%, TPS drops to ~210, $PAY1 queue builds to ~1,800, no I/O from $PAY1",
        "root_cause": "$PAY1 primary process stuck in a loop",
        "fix_action": "Operator checks STATUS $PAY1, then SWITCH $PAY1 to backup on CPU 3 (senior sign-off)",
        "demo": True,
    },
    {
        "id": "INC-002",
        "title": "CPU 3 hardware failure, capacity reduced",
        "start": hhmm(14, 30), "fix": hhmm(14, 55), "end": hhmm(15, 10),
        "severity": "CRITICAL",
        "symptoms": "CPU 3 at 0%, takeover to CPU 1, CPU 1 load ~90%, response time doubles",
        "root_cause": "CPU 3 hardware fault; process pairs took over on remaining CPUs",
        "fix_action": "Confirm takeover with PEEK and STATUS, call hardware support, rebalance load (senior)",
        "demo": False,
    },
    {
        "id": "INC-003",
        "title": "Disk $DATA01 filling up",
        "start": hhmm(19, 0), "fix": hhmm(20, 40), "end": hhmm(20, 50),
        "severity": "MEDIUM",
        "symptoms": "$DATA01 climbs from ~72% to ~93%",
        "root_cause": "Audit trail files growing faster than they are purged",
        "fix_action": "FUP INFO to find large audit files, purge per runbook (caution)",
        "demo": False,
    },
]


def phase(minute, inc):
    """Return 'normal', 'active', 'recovering' for a minute vs an incident."""
    if inc["start"] <= minute < inc["fix"]:
        return "active"
    if inc["fix"] <= minute < inc["end"]:
        return "recovering"
    return "normal"


# ---------------------------------------------------------------------------
# 2. Metrics, one row per minute
# ---------------------------------------------------------------------------
def generate_day(rng, with_incidents=True, date=START):
    """One day of minute-level metrics. with_incidents=False gives a clean normal day."""
    rows = []
    disk = 70.0
    for m in range(MINUTES):
        hour = m / 60
        # daily shape: quieter at night, busier around midday
        day = 0.5 * (1 + np.sin((hour - 9) / 24 * 2 * np.pi))  # 0..1
        tps = 480 + 220 * day + rng.normal(0, 18)
        base_cpu = 28 + 22 * day
        cpu = [base_cpu + rng.normal(0, 3) for _ in range(4)]
        resp = 45 + 15 * day + rng.normal(0, 3)
        queue = max(0, rng.normal(10, 4))
        backout = max(0, rng.normal(0.2, 0.08))
        pay1_io_age = rng.uniform(0, 3)  # seconds since last I/O
        disk += rng.normal(0.0005, 0.002)

        i1, i2, i3 = INCIDENTS
        p1, p2, p3 = (phase(m, i1), phase(m, i2), phase(m, i3)) if with_incidents else ("normal",) * 3

        # INC-001: $PAY1 loop on CPU 2
        if p1 == "active":
            k = min(1.0, (m - i1["start"]) / 3)
            cpu[2] = 96 + rng.normal(0, 1.5)
            tps = tps * (1 - 0.6 * k) + rng.normal(0, 8)
            queue = 200 + 165 * (m - i1["start"]) + rng.normal(0, 30)
            resp = resp * (1 + 2.5 * k)
            pay1_io_age = 60 * (m - i1["start"]) + rng.uniform(0, 30)
        elif p1 == "recovering":
            k = (m - i1["fix"]) / (i1["end"] - i1["fix"])
            cpu[3] = cpu[3] + 20 * (1 - k)
            queue = max(10, 1800 * (1 - k) ** 2)
            resp = resp * (1 + 0.8 * (1 - k))

        # INC-002: CPU 3 down, takeover to CPU 1
        if p2 == "active":
            cpu[1] = min(97, cpu[1] + cpu[3] + 10 + rng.normal(0, 2))
            cpu[3] = 0.0
            resp = resp * 2.1
            tps = tps * 0.82
            backout = backout + 1.5 + rng.normal(0, 0.3)
        elif p2 == "recovering":
            k = (m - i2["fix"]) / (i2["end"] - i2["fix"])
            cpu[3] = cpu[3] * k
            cpu[1] = cpu[1] + 25 * (1 - k)
            resp = resp * (1 + 0.6 * (1 - k))

        # INC-003: disk filling
        if p3 == "active":
            disk += 0.21
        elif p3 == "recovering":
            disk = max(72.0, disk - 2.2)

        rows.append({
            "time": (date + timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M"),
            "cpu0_pct": round(float(np.clip(cpu[0], 0, 100)), 1),
            "cpu1_pct": round(float(np.clip(cpu[1], 0, 100)), 1),
            "cpu2_pct": round(float(np.clip(cpu[2], 0, 100)), 1),
            "cpu3_pct": round(float(np.clip(cpu[3], 0, 100)), 1),
            "tps": int(max(0, tps)),
            "response_ms": round(float(max(5, resp)), 1),
            "pay1_queue": int(max(0, queue)),
            "pay1_last_io_sec": round(float(pay1_io_age), 1),
            "disk_data01_pct": round(float(np.clip(disk, 0, 100)), 2),
            "tmf_backout_pct": round(float(backout), 2),
        })

    return pd.DataFrame(rows)


# TEST day: the day we analyse and demo (with the 3 incidents)
df = generate_day(rng, with_incidents=True)

# TRAINING day: a separate clean normal day (different random seed, day before).
# Isolation Forest learns "normal" from this day only, then scores the test day.
train_df = generate_day(np.random.default_rng(SEED + 1), with_incidents=False,
                        date=START - timedelta(days=1))

# ---------------------------------------------------------------------------
# 3. EMS-style events
# ---------------------------------------------------------------------------
def ev(minute, sev, subsystem, msg, inc=None):
    return {"time": t(minute).strftime("%Y-%m-%dT%H:%M"), "severity": sev,
            "subsystem": subsystem, "node": NODE, "message": msg, "incident": inc}

events = [
    ev(hhmm(0, 0), "INFO", "TMF", "TMF audit trail rollover complete"),
    ev(hhmm(1, 30), "INFO", "SPOOLER", "Nightly batch report printed"),
    # INC-001
    ev(hhmm(2, 14), "WARN", "CPU 2", "Process $PAY1 high CPU usage (96%)", "INC-001"),
    ev(hhmm(2, 15), "WARN", "TMF", "Transaction rate below threshold (210 tps)", "INC-001"),
    ev(hhmm(2, 17), "WARN", "PATHWAY", "Server class PAY-SVR request queue growing", "INC-001"),
    ev(hhmm(2, 23), "INFO", "AUDIT", "Operator jr-ops-03 requested senior sign-off for SWITCH $PAY1", "INC-001"),
    ev(hhmm(2, 24), "INFO", "OPERATOR", "SWITCH $PAY1 approved by R. Diaz, executed by jr-ops-03", "INC-001"),
    ev(hhmm(2, 24), "INFO", "CPU 3", "$PAY1 backup in CPU 3 has taken over", "INC-001"),
    ev(hhmm(2, 34), "INFO", "TMF", "Transaction rate normal (492 tps)", "INC-001"),
    ev(hhmm(6, 0), "INFO", "TMF", "Online dump started"),
    ev(hhmm(6, 40), "INFO", "TMF", "Online dump complete"),
    # INC-002
    ev(hhmm(14, 30), "CRIT", "CPU 3", "CPU 3 down: hardware fault detected", "INC-002"),
    ev(hhmm(14, 30), "WARN", "CPU 1", "Process pairs taken over from CPU 3", "INC-002"),
    ev(hhmm(14, 33), "WARN", "TMF", "Backout rate elevated (1.7%)", "INC-002"),
    ev(hhmm(14, 40), "WARN", "CPU 1", "CPU 1 sustained load above 90%", "INC-002"),
    ev(hhmm(14, 55), "INFO", "OPERATOR", "CPU 3 reloaded after hardware support call", "INC-002"),
    ev(hhmm(15, 10), "INFO", "TMF", "Backout rate normal", "INC-002"),
    # INC-003
    ev(hhmm(19, 40), "WARN", "DISK", "$DATA01 above 80% capacity", "INC-003"),
    ev(hhmm(20, 25), "WARN", "DISK", "$DATA01 above 90% capacity", "INC-003"),
    ev(hhmm(20, 40), "INFO", "OPERATOR", "Old audit files purged on $DATA01", "INC-003"),
    ev(hhmm(23, 0), "INFO", "TMF", "TMF audit trail rollover complete"),
]

# Tag each event with the monitoring tool that would raise it in a real bank,
# and a severity rank (1 = most urgent). In production these alerts come from
# tools like MOMI, ASAP, Prognosis or ViewSys; CAIL Relay reads them, it does not replace them.
TOOL_BY_SUBSYSTEM = {"CPU 1": "ASAP", "CPU 2": "ASAP", "CPU 3": "ASAP", "DISK": "ViewSys",
                     "TMF": "Prognosis", "PATHWAY": "Prognosis"}
RANK = {"CRIT": 1, "WARN": 2, "INFO": 4}
for e in events:
    tool = TOOL_BY_SUBSYSTEM.get(e["subsystem"])
    if e["message"].startswith("Process") or "Process pairs" in e["message"]:
        tool = "MOMI"  # MOMI (BrightStrand) monitors processes on NonStop
    e["source"] = f"{tool} (simulated)" if tool else "EMS (simulated)"
    rank = RANK[e["severity"]]
    if e["severity"] == "WARN" and e["subsystem"] == "DISK" and "80%" in e["message"]:
        rank = 3  # early disk warning: medium
    e["severity_rank"] = rank

# ---------------------------------------------------------------------------
# 4. Anomaly detection
#    a) rolling z-score per metric vs the previous 60 minutes
#    b) Isolation Forest across all metrics (if scikit-learn is installed)
# ---------------------------------------------------------------------------
FEATURES = ["cpu0_pct", "cpu1_pct", "cpu2_pct", "cpu3_pct", "tps",
            "response_ms", "pay1_queue", "disk_data01_pct", "tmf_backout_pct"]

Z_LIMIT = 4.0
z_flags = pd.DataFrame(index=df.index)
for col in FEATURES:
    base = df[col].shift(1).rolling(60, min_periods=30)
    z = (df[col] - base.mean()) / (base.std() + 1e-6)
    z_flags[col] = z.abs() > Z_LIMIT
df["z_anomaly"] = z_flags.any(axis=1)
df["z_metrics"] = z_flags.apply(lambda r: [c for c in FEATURES if r[c]], axis=1)

# c) trend detector for slow drift (z-score misses slow changes because its
#    baseline moves with the drift). Flag if disk RISES faster than 0.05%/min
#    over the last 15 minutes (normal growth is ~0.002%/min), or is above 85%.
slope = df["disk_data01_pct"].diff(15) / 15
df["trend_anomaly"] = (slope > 0.05) | (df["disk_data01_pct"] > 85)
df.loc[df["trend_anomaly"], "z_metrics"] = df.loc[df["trend_anomaly"], "z_metrics"].apply(
    lambda l: sorted(set(l) | {"disk_data01_pct"}))

try:
    from sklearn.ensemble import IsolationForest
    # Preprocessing: standardise each metric using the TRAINING day's mean/std
    mu, sd = train_df[FEATURES].mean(), train_df[FEATURES].std() + 1e-6
    X_train = (train_df[FEATURES] - mu) / sd
    X_test = (df[FEATURES] - mu) / sd
    # Train on the normal day only (no labels, no incidents)
    iso = IsolationForest(n_estimators=200, random_state=SEED).fit(X_train)
    train_scores = -iso.score_samples(X_train)
    threshold = np.percentile(train_scores, 99.5)  # top 0.5% of NORMAL = limit
    # Test: score the unseen incident day
    df["iso_score"] = -iso.score_samples(X_test)
    df["iso_anomaly"] = df["iso_score"] > threshold
    iso_threshold = float(threshold)
    method = "rolling z-score + Isolation Forest + trend check"
except ImportError:
    df["iso_anomaly"] = False
    df["iso_score"] = 0.0
    iso_threshold = None
    method = "rolling z-score (install scikit-learn for Isolation Forest)"

df["anomaly"] = df["z_anomaly"] | df["iso_anomaly"] | df["trend_anomaly"]

# group consecutive anomalous minutes into windows (allow 3-min gaps)
windows, cur = [], None
for i, flag in enumerate(df["anomaly"]):
    if flag:
        if cur and i - cur["end_i"] <= 3:
            cur["end_i"] = i
        else:
            cur = {"start_i": i, "end_i": i}
            windows.append(cur)
anomalies = []
for w in windows:
    if w["end_i"] - w["start_i"] < 2:  # ignore 1-2 minute blips
        continue
    seg = df.iloc[w["start_i"]: w["end_i"] + 1]
    mets = sorted({m for lst in seg["z_metrics"] for m in lst})
    linked = next((inc["id"] for inc in INCIDENTS
                   if inc["start"] - 5 <= w["start_i"] <= inc["end"]), None)
    anomalies.append({
        "start": seg["time"].iloc[0], "end": seg["time"].iloc[-1],
        "minutes": len(seg), "metrics": mets,
        "max_score": round(float(seg["iso_score"].max()), 3),
        "incident": linked,
    })

# detection lead time vs first EMS warning, per incident
for inc in INCIDENTS:
    first_alert = min(e["time"] for e in events if e["incident"] == inc["id"])
    first_anom = next((a["start"] for a in anomalies if a["incident"] == inc["id"]), None)
    inc["first_ems_alert"] = first_alert
    inc["first_detected"] = first_anom
    for k in ("start", "fix", "end"):
        inc[k] = t(inc[k]).strftime("%Y-%m-%dT%H:%M")

# ---------------------------------------------------------------------------
# 5. Simulated command catalog + outputs (illustrative syntax)
# ---------------------------------------------------------------------------
commands = {
    "STATUS $PAY1, DETAIL": {
        "risk": "SAFE", "changes_system": False,
        "purpose": "Show state, load, queue and backup of the payment server process",
        "source": "TACL Reference Manual: STATUS",
        "output": {
            "during_INC-001": [
                "Process  $PAY1      CPU 2    Pri 150    State RUNNING",
                "Busy     96%        Msgs queued 1,842",
                "Last I/O 00:06:12 ago",
                "Backup   CPU 3      Status READY",
            ],
            "normal": [
                "Process  $PAY1      CPU 3    Pri 150    State RUNNING",
                "Busy     31%        Msgs queued 12",
                "Last I/O 00:00:01 ago",
                "Backup   CPU 2      Status READY",
            ],
        },
    },
    "PEEK /CPU 2/": {
        "risk": "SAFE", "changes_system": False,
        "purpose": "Show CPU 2 load and memory",
        "source": "PEEK Reference Manual",
        "output": {
            "during_INC-001": ["CPU 2  Busy 96%  Dispatches/s 18,400  Mem used 71%"],
            "normal": ["CPU 2  Busy 34%  Dispatches/s 6,200  Mem used 58%"],
        },
    },
    "PEEK /CPU 3/": {
        "risk": "SAFE", "changes_system": False,
        "purpose": "Show CPU 3 load and memory",
        "source": "PEEK Reference Manual",
        "output": {
            "during_INC-002": ["CPU 3  *** CPU DOWN ***"],
            "normal": ["CPU 3  Busy 33%  Dispatches/s 6,050  Mem used 57%"],
        },
    },
    "SCF STATUS DISK $DATA01": {
        "risk": "SAFE", "changes_system": False,
        "purpose": "Check disk volume health and usage",
        "source": "SCF Reference Manual: STATUS DISK",
        "output": {
            "during_INC-003": ["$DATA01  STARTED  Primary/Mirror OK  Used 93%"],
            "normal": ["$DATA01  STARTED  Primary/Mirror OK  Used 72%"],
        },
    },
    "FUP INFO $DATA01.AUDIT.*": {
        "risk": "SAFE", "changes_system": False,
        "purpose": "List audit files and sizes on $DATA01",
        "source": "FUP Reference Manual: INFO",
        "output": {
            "during_INC-003": [
                "AA000412   EOF 2,048 MB   Last mod 2026-10-10",
                "AA000413   EOF 2,048 MB   Last mod 2026-10-11",
                "AA000414   EOF 1,920 MB   Last mod 2026-10-17",
            ],
        },
    },
    "TMFCOM STATUS TMF": {
        "risk": "SAFE", "changes_system": False,
        "purpose": "Check the transaction management system",
        "source": "TMF Reference Manual: TMFCOM",
        "output": {
            "during_INC-001": ["TMF STARTED  Transactions/s 210  Backout 0.2%"],
            "during_INC-002": ["TMF STARTED  Transactions/s 470  Backout 1.7%"],
            "normal": ["TMF STARTED  Transactions/s 492  Backout 0.2%"],
        },
    },
    "PATHCOM STATUS SERVER PAY-SVR": {
        "risk": "SAFE", "changes_system": False,
        "purpose": "Check the payment application server class",
        "source": "Pathway Reference Manual: PATHCOM",
        "output": {
            "during_INC-001": ["PAY-SVR  RUNNING  Links 8  Requests queued 1,842"],
            "normal": ["PAY-SVR  RUNNING  Links 8  Requests queued 12"],
        },
    },
    "SWITCH $PAY1": {
        "risk": "HIGH RISK", "changes_system": True, "needs_senior": True,
        "purpose": "Move $PAY1 to its backup process on CPU 3",
        "impact": "Payments pause about 2 seconds during takeover",
        "source": "Runbook RB-012 (senior note)",
        "output": {
            "during_INC-001": [
                "$PAY1 primary stopped. Backup in CPU 3 has taken over.",
                "EMS: Transaction rate normal (492 tps)",
            ],
        },
    },
    "PURGE $DATA01.AUDIT.AA000412": {
        "risk": "CAUTION", "changes_system": True, "needs_senior": False,
        "purpose": "Delete an old audit file that is already archived",
        "impact": "Irreversible. Only purge files confirmed archived",
        "source": "Runbook RB-031",
        "output": {"during_INC-003": ["File purged. $DATA01 Used 81%"]},
    },
}

# ---------------------------------------------------------------------------
# 5b. Users, roles and permissions (simulated; in production from the bank's
#     identity system, e.g. Active Directory / Safeguard on NonStop)
# ---------------------------------------------------------------------------
users = {
    "roles": {
        "junior_operator": {
            "label": "Junior Operator",
            "can_run": ["SAFE"],
            "needs_confirmation": ["CAUTION"],
            "needs_senior_approval": ["HIGH RISK"],
            "can_approve_others": False,
            "can_add_knowledge": False,
        },
        "senior_operator": {
            "label": "Senior Operator",
            "can_run": ["SAFE", "CAUTION", "HIGH RISK"],
            "needs_confirmation": ["CAUTION", "HIGH RISK"],
            "needs_senior_approval": [],
            "can_approve_others": True,
            "can_add_knowledge": True,
            "can_review_knowledge": True,
        },
        "ops_manager": {
            "label": "Operations Manager",
            "can_run": [],
            "needs_confirmation": [],
            "needs_senior_approval": [],
            "can_approve_others": False,
            "can_add_knowledge": True,
            "can_view_audit_log": True,
        },
    },
    "users": [
        {"id": "jr-ops-03", "name": "Sam Lee", "role": "junior_operator", "shift": "night", "on_call": False},
        {"id": "sr-rdiaz", "name": "R. Diaz", "role": "senior_operator", "shift": "night", "on_call": True},
        {"id": "sr-mchen", "name": "M. Chen", "role": "senior_operator", "shift": "day", "on_call": False},
        {"id": "mgr-kosei", "name": "K. Osei", "role": "ops_manager", "shift": "day", "on_call": False},
    ],
    "rules": [
        "Nothing runs without a human clicking Approve.",
        "Junior operators can run SAFE (read-only) commands after approving them.",
        "CAUTION commands need an extra confirmation step.",
        "HIGH RISK commands from a junior need sign-off from an on-call senior operator.",
        "Only senior operators can approve another operator's request or submit notes to the knowledge base.",
        "A new knowledge entry needs a second, different senior to approve it (two-person review).",
        "Every request, approval, rejection and command is written to the audit log.",
    ],
    "note": "Simulated for Catalyst 2026. Names are fictional.",
}

# ---------------------------------------------------------------------------
# 5c. Knowledge base with two-person (four-eyes) review
#     A fix that is not in the manuals or existing runbooks is SUBMITTED by
#     senior A and only becomes "approved" after a DIFFERENT senior B reviews it.
#     The AI uses approved entries; pending ones are shown as "unverified".
# ---------------------------------------------------------------------------
knowledge = {
    "review_rules": [
        "Only senior operators can submit a new fix to the knowledge base.",
        "A submission needs approval from a second, different senior operator before it is used.",
        "The submitter can never approve their own submission.",
        "The AI only cites APPROVED entries as guidance. PENDING entries are shown as 'unverified, awaiting review'.",
        "Rejected entries are kept in the audit log with the reviewer's reason.",
    ],
    "entries": [
        {"id": "RB-009", "title": "CPU down: check capacity before restart", "incident_type": "cpu_failure",
         "steps": ["PEEK each remaining CPU to confirm takeover and load",
                   "TMFCOM STATUS TMF to check backouts",
                   "Call hardware support; do not reload the CPU yourself",
                   "If any CPU stays above 90% for 10+ minutes, escalate to rebalance load"],
         "source_type": "senior_note", "status": "approved",
         "submitted_by": "sr-mchen", "submitted_at": "2026-09-02T10:15",
         "reviewed_by": "sr-rdiaz", "reviewed_at": "2026-09-02T16:40", "times_used": 18},
        {"id": "RB-012", "title": "Looping payment server: switch to backup", "incident_type": "process_loop",
         "steps": ["STATUS $PAY1, DETAIL: check busy %, queue and last I/O",
                   "If busy > 90%, queue growing and no I/O for 5+ minutes, it is looping",
                   "Confirm the backup process is READY",
                   "SWITCH $PAY1 (HIGH RISK, senior sign-off)"],
         "source_type": "senior_note", "status": "approved",
         "submitted_by": "sr-rdiaz", "submitted_at": "2026-08-14T03:05",
         "reviewed_by": "sr-mchen", "reviewed_at": "2026-08-14T09:20", "times_used": 31},
        {"id": "RB-031", "title": "Disk over 90%: find large audit files first", "incident_type": "disk_full",
         "steps": ["SCF STATUS DISK $DATA01", "FUP INFO $DATA01.AUDIT.* to list large files",
                   "Purge only files confirmed archived (CAUTION)"],
         "source_type": "past_incident", "status": "approved",
         "submitted_by": "sr-mchen", "submitted_at": "2026-07-21T20:55",
         "reviewed_by": "sr-rdiaz", "reviewed_at": "2026-07-22T08:10", "times_used": 12},
        {"id": "RB-048", "title": "TMF backouts stay high after CPU takeover: wait before acting",
         "incident_type": "cpu_failure",
         "steps": ["After a CPU takeover, backouts often spike for a few minutes while backups warm up",
                   "Wait 5 minutes and re-check TMFCOM STATUS TMF before taking any action",
                   "If still above 1%, check the audit trail volume, not the application"],
         "source_type": "senior_note", "status": "pending",
         "submitted_by": "sr-rdiaz", "submitted_at": "2026-10-17T15:12",
         "reviewed_by": None, "reviewed_at": None, "times_used": 0,
         "note": "New fix from INC-002, not in manuals or existing runbooks. Awaiting review by a second senior (e.g. M. Chen)."},
        {"id": "RB-044", "title": "Restart $PAY1 instead of switching",
         "incident_type": "process_loop",
         "steps": ["STOP $PAY1 and restart it"],
         "source_type": "senior_note", "status": "rejected",
         "submitted_by": "sr-mchen", "submitted_at": "2026-09-30T02:40",
         "reviewed_by": "sr-rdiaz", "reviewed_at": "2026-09-30T08:05", "times_used": 0,
         "review_reason": "Stopping the primary drops in-flight payments; SWITCH to the backup is safer (see RB-012)."},
    ],
    "note": "Simulated for Catalyst 2026.",
}

# ---------------------------------------------------------------------------
# 6. Export
# ---------------------------------------------------------------------------
def dump(name, obj):
    with open(os.path.join(OUT, name), "w") as f:
        json.dump(obj, f, indent=1, default=str)

metrics_out = df.drop(columns=["z_metrics"]).copy()
metrics_out["iso_score"] = metrics_out["iso_score"].round(3)
dump("metrics.json", metrics_out.to_dict(orient="records"))
dump("events.json", events)
dump("incidents.json", INCIDENTS)
dump("anomalies.json", anomalies)
dump("commands.json", commands)
dump("users.json", users)
dump("knowledge.json", knowledge)
dump("summary.json", {
    "node": NODE, "start": df["time"].iloc[0], "end": df["time"].iloc[-1],
    "minutes": MINUTES, "detection_method": method,
    "incidents": len(INCIDENTS), "anomaly_windows": len(anomalies),
    "train_day": train_df["time"].iloc[0][:10], "test_day": df["time"].iloc[0][:10],
    "iso_threshold": iso_threshold,
    "note": "All data simulated for Catalyst 2026. Command syntax illustrative; verify against HPE NonStop manuals.",
})

# chart for the pitch
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = pd.to_datetime(df["time"])
    fig, axes = plt.subplots(3, 1, figsize=(12, 7), sharex=True)
    axes[0].plot(x, df["tps"], lw=0.8, color="#2F6DB5"); axes[0].set_ylabel("TPS")
    for c, col in zip(["cpu1_pct", "cpu2_pct", "cpu3_pct"], ["#888", "#D9822B", "#1E8C7A"]):
        axes[1].plot(x, df[c], lw=0.8, label=c.replace("_pct", ""), color=col)
    axes[1].set_ylabel("CPU %"); axes[1].legend(loc="upper right", fontsize=8)
    axes[2].plot(x, df["disk_data01_pct"], lw=0.8, color="#5A6472"); axes[2].set_ylabel("$DATA01 %")
    for a in anomalies:
        for ax in axes:
            ax.axvspan(pd.to_datetime(a["start"]), pd.to_datetime(a["end"]), color="#C0392B", alpha=0.15)
    axes[0].set_title("Simulated \\PROD1, 24h. Red bands = detected anomalies")
    fig.tight_layout(); fig.savefig(os.path.join(OUT, "chart.png"), dpi=150)
except ImportError:
    pass

print(f"Done. {MINUTES} minutes, {len(events)} events, {len(anomalies)} anomaly windows.")
print(f"Detection: {method}")
for a in anomalies:
    print(f"  {a['start'][11:]} - {a['end'][11:]}  {a['incident'] or 'unlinked':8}  {', '.join(a['metrics'])}")
print(f"Files written to ./{OUT}/")
