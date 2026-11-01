import sqlite3
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sklearn.ensemble import IsolationForest

DB_PATH = Path(__file__).with_name("electricity_theft_monitor.db")

REQUIRED_COLUMNS = ["day", "consumer_id", "expected_kwh", "meter_kwh"]
REPORT_COLS = [
    "day",
    "consumer_id",
    "category",
    "expected_kwh",
    "meter_kwh",
    "deviation_pct",
    "severity",
    "detected_by",
    "reason",
]


def make_demo_data(n_cons=30, n_days=14, seed=42):
    rng = np.random.default_rng(seed)
    days = pd.date_range("2024-01-01", periods=n_days, freq="D")
    categories = np.array(["Residential", "Commercial", "Industrial"])
    rows = []
    truth_rows = []

    for d_idx, day in enumerate(days):
        for c_idx in range(1, n_cons + 1):
            cid = f"C-{c_idx:03d}"
            cat = categories[(c_idx - 1) % len(categories)]

            base = 20 + (c_idx * 3.5) + (d_idx * 1.2)
            if cat == "Commercial":
                base *= 1.5
            elif cat == "Industrial":
                base *= 2.3

            expected = float(base + rng.normal(0, 7))
            expected = max(expected, 5.0)

            kind = "normal"
            meter = expected * (1 + rng.normal(0, 0.12))

            if rng.random() < 0.09:
                kind = np.random.choice(["bypass", "meter_fault", "spike"], p=[0.55, 0.25, 0.20])
                if kind == "bypass":
                    meter = expected * (0.20 + rng.random() * 0.55)
                elif kind == "meter_fault":
                    meter = 0.0
                else:
                    meter = expected * (1.5 + rng.random() * 2.2)

            meter = max(0.0, meter)
            rows.append({
                "day": pd.Timestamp(day).normalize(),
                "consumer_id": cid,
                "expected_kwh": round(expected, 2),
                "meter_kwh": round(meter, 2),
                "category": cat,
            })

            if kind != "normal":
                truth_rows.append({
                    "day": pd.Timestamp(day).normalize(),
                    "consumer_id": cid,
                    "kind": kind,
                })

    raw = pd.DataFrame(rows)
    truth = pd.DataFrame(truth_rows)
    if not truth.empty:
        truth = truth.drop_duplicates(subset=["day", "consumer_id"], keep="last").reset_index(drop=True)

    return raw, truth


def validate(raw_df):
    errors = []
    if raw_df is None or raw_df.empty:
        errors.append("No data available.")
        return pd.DataFrame(columns=REQUIRED_COLUMNS), errors, 0

    clean = raw_df.copy()

    missing = [c for c in REQUIRED_COLUMNS if c not in clean.columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")
        return pd.DataFrame(columns=REQUIRED_COLUMNS), errors, len(clean)

    clean["day"] = pd.to_datetime(clean["day"], errors="coerce")
    clean["consumer_id"] = clean["consumer_id"].astype(str).str.strip()
    clean["expected_kwh"] = pd.to_numeric(clean["expected_kwh"], errors="coerce")
    clean["meter_kwh"] = pd.to_numeric(clean["meter_kwh"], errors="coerce")

    valid_mask = (
        clean["day"].notna()
        & clean["consumer_id"].ne("")
        & clean["expected_kwh"].notna()
        & clean["meter_kwh"].notna()
        & (clean["expected_kwh"] >= 0)
        & (clean["meter_kwh"] >= 0)
    )

    dropped_count = int((~valid_mask).sum())
    clean = clean.loc[valid_mask].copy()
    clean = clean.sort_values(["day", "consumer_id"]).reset_index(drop=True)

    if "category" not in clean.columns:
        clean["category"] = "Unknown"

    if clean.empty:
        errors.append("No valid rows remain after validation.")

    return clean, errors, dropped_count


def _safe_pct_delta(meter, expected):
    if pd.isna(expected) or expected == 0:
        return 0.0
    return ((meter - expected) / expected) * 100.0


def analyse(clean, threshold=25.0, contamination=0.04):
    df = clean.copy()
    if df.empty:
        return pd.DataFrame(columns=[
            "day", "consumer_id", "category", "expected_kwh", "meter_kwh",
            "deviation_pct", "flagged", "severity", "detected_by", "reason", "anomaly_score"
        ])

    df["day"] = pd.to_datetime(df["day"]).dt.normalize()
    df["expected_kwh"] = pd.to_numeric(df["expected_kwh"], errors="coerce").fillna(0)
    df["meter_kwh"] = pd.to_numeric(df["meter_kwh"], errors="coerce").fillna(0)
    df["deviation_pct"] = np.vectorize(_safe_pct_delta)(df["meter_kwh"], df["expected_kwh"])
    df["rule_flag"] = np.abs(df["deviation_pct"]) >= float(threshold)

    ml_flags = []
    ml_scores = []

    for consumer_id, g in df.groupby("consumer_id", sort=False):
        features = g[["expected_kwh", "meter_kwh"]].copy()
        features["ratio"] = np.clip(g["meter_kwh"] / g["expected_kwh"].replace(0, 1), 0, 5)

        if len(features) < 5:
            g_ml_flag = pd.Series(False, index=g.index)
            g_ml_score = pd.Series(0.0, index=g.index)
        else:
            model = IsolationForest(contamination=float(np.clip(contamination, 0.01, 0.15)), random_state=42)
            model.fit(features)
            g_ml_flag = pd.Series(model.predict(features) == -1, index=g.index)
            g_ml_score = pd.Series(-model.score_samples(features), index=g.index)

        ml_flags.append(g_ml_flag)
        ml_scores.append(g_ml_score)

    df["ml_flag"] = pd.concat(ml_flags).sort_index()
    df["ml_score"] = pd.concat(ml_scores).sort_index().fillna(0)

    df["flagged"] = df["rule_flag"] | df["ml_flag"]
    df["anomaly_score"] = np.abs(df["deviation_pct"]) + df["ml_score"].fillna(0)

    def detect_by(row):
        if row["rule_flag"] and row["ml_flag"]:
            return "Rule + ML"
        if row["rule_flag"]:
            return "Rule"
        if row["ml_flag"]:
            return "ML"
        return "Normal"

    def reason_for(row):
        if not row["flagged"]:
            return "Normal reading"
        parts = []
        if row["rule_flag"]:
            parts.append(f"Deviation {row['deviation_pct']:.1f}% from expected")
        if row["ml_flag"]:
            parts.append("historical consumption pattern is unusual")
        return "; ".join(parts)

    df["detected_by"] = df.apply(detect_by, axis=1)
    df["reason"] = df.apply(reason_for, axis=1)

    def severity_for(row):
        if not row["flagged"]:
            return "Normal"
        if abs(row["deviation_pct"]) >= max(float(threshold) * 2, 30):
            return "High"
        if abs(row["deviation_pct"]) >= float(threshold):
            return "Medium"
        return "Low"

    df["severity"] = df.apply(severity_for, axis=1)

    return df[
        [
            "day",
            "consumer_id",
            "category",
            "expected_kwh",
            "meter_kwh",
            "deviation_pct",
            "flagged",
            "severity",
            "detected_by",
            "reason",
            "anomaly_score",
        ]
    ].reset_index(drop=True)


def feeder_balance(a, tech_loss=6.0, tolerance=3.0, override=None):
    if a is None or a.empty:
        return pd.DataFrame(columns=[
            "day", "supplied_kwh", "recorded_kwh", "tech_loss_kwh",
            "unexplained_kwh", "total_loss_pct", "unexplained_pct", "warning"
        ])

    df = a.copy()
    df["day"] = pd.to_datetime(df["day"]).dt.normalize()

    supply_series = (
        df.groupby("day", as_index=False)["expected_kwh"].sum()
        .rename(columns={"expected_kwh": "supplied_kwh"})
    )
    recorded_series = df.groupby("day", as_index=False)["meter_kwh"].sum().rename(columns={"meter_kwh": "recorded_kwh"})

    balance = supply_series.merge(recorded_series, on="day", how="outer")
    if override:
        balance["supplied_kwh"] = float(override)

    balance["supplied_kwh"] = balance["supplied_kwh"].fillna(0)
    balance["recorded_kwh"] = balance["recorded_kwh"].fillna(0)

    tech_loss_pct = float(tech_loss) / 100.0
    balance["tech_loss_kwh"] = balance["supplied_kwh"] * tech_loss_pct
    balance["total_loss_kwh"] = balance["supplied_kwh"] - balance["recorded_kwh"]
    balance["unexplained_kwh"] = np.maximum(
        balance["supplied_kwh"] - balance["recorded_kwh"] - balance["tech_loss_kwh"],
        0.0,
    )
    balance["total_loss_pct"] = np.where(
        balance["supplied_kwh"] > 0,
        (balance["supplied_kwh"] - balance["recorded_kwh"]) / balance["supplied_kwh"] * 100.0,
        0.0,
    )
    balance["unexplained_pct"] = np.where(
        balance["supplied_kwh"] > 0,
        balance["unexplained_kwh"] / balance["supplied_kwh"] * 100.0,
        0.0,
    )
    balance["warning"] = balance["unexplained_pct"] > float(tolerance)

    balance = balance.sort_values("day").reset_index(drop=True)
    return balance[
        [
            "day",
            "supplied_kwh",
            "recorded_kwh",
            "tech_loss_kwh",
            "unexplained_kwh",
            "total_loss_pct",
            "unexplained_pct",
            "warning",
        ]
    ]


def consumer_summary(analysed):
    if analysed is None or analysed.empty:
        return pd.DataFrame(columns=["consumer_id", "category", "avg_deviation_pct", "flagged_days", "risk"])

    summary = (
        analysed.groupby("consumer_id", as_index=False)
        .agg(
            category=("category", "first"),
            avg_deviation_pct=("deviation_pct", "mean"),
            flagged_days=("flagged", "sum"),
        )
        .sort_values(["flagged_days", "avg_deviation_pct"], ascending=[False, False])
    )

    def risk_label(row):
        if row["flagged_days"] >= 5:
            return "Priority review"
        if row["flagged_days"] >= 2:
            return "Watch"
        return "Normal"

    summary["risk"] = summary.apply(risk_label, axis=1)
    return summary


def alerts_to_csv(rep):
    return rep.to_csv(index=False).encode()


def alerts_to_pdf(rep, balance, settings=None):
    if rep is None or rep.empty:
        rep = pd.DataFrame(columns=REPORT_COLS)

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Electricity Theft Detection Report", styles["Title"]))
    story.append(Spacer(1, 18))

    if settings:
        story.append(Paragraph(f"Threshold: {settings.get('threshold', 'N/A')}%"))
        story.append(Paragraph(f"Technical loss: {settings.get('tech_loss', 'N/A')}%"))
        story.append(Spacer(1, 12))

    if not rep.empty:
        total_supply = float(balance["supplied_kwh"].sum()) if "supplied_kwh" in balance.columns else 0
        total_recorded = float(balance["recorded_kwh"].sum()) if "recorded_kwh" in balance.columns else 0
        story.append(Paragraph(f"Total supply: {total_supply:,.0f} kWh"))
        story.append(Paragraph(f"Total recorded: {total_recorded:,.0f} kWh"))
        story.append(Paragraph(f"Alerts included: {len(rep)}"))
        story.append(Spacer(1, 18))

        table_data = [
            ["Day", "Consumer", "Category", "Expected", "Meter", "Deviation %", "Severity", "Detected by"]
        ]
        for _, r in rep.head(25).iterrows():
            table_data.append([
                str(pd.Timestamp(r["day"]).strftime("%Y-%m-%d")),
                str(r["consumer_id"]),
                str(r["category"]),
                f"{r['expected_kwh']:.1f}",
                f"{r['meter_kwh']:.1f}",
                f"{r['deviation_pct']:.1f}",
                str(r["severity"]),
                str(r["detected_by"]),
            ])

        tbl = Table(table_data, colWidths=[60, 70, 70, 60, 60, 60, 55, 70])
        tbl.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(tbl)
    else:
        story.append(Paragraph("No alerts to report at the current settings."))

    doc.build(story)
    return buffer.getvalue()


def save_to_db(data, alerts, db_path=None):
    path = Path(db_path) if db_path is not None else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        if data is not None and not data.empty:
            data.to_sql("readings", conn, index=False, if_exists="replace")
        if alerts is not None and not alerts.empty:
            alerts.to_sql("alerts", conn, index=False, if_exists="replace")
    finally:
        conn.close()


def load_from_db(db_path=None):
    path = Path(db_path) if db_path is not None else DB_PATH
    if not path.exists():
        return None

    conn = sqlite3.connect(path)
    try:
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        if "readings" not in tables:
            return None
        data = pd.read_sql_query("SELECT * FROM readings", conn)
    finally:
        conn.close()

    return data if not data.empty else None
