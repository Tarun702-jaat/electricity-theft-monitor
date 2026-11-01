import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import engine as E

st.set_page_config(page_title="POWERGUARD GLOBAL", page_icon="⚡", layout="wide")

BLUE = "#2563eb"
ORANGE = "#f59e0b"
RED = "#dc2626"
GREEN = "#16a34a"
GREY = "#94a3b8"
NAVY = "#0b132b"
SLATE = "#1f2937"
SEV_COLOR = {"High": RED, "Medium": ORANGE, "Low": "#eab308", "Normal": GREEN}

st.markdown(
    """
    <style>
        :root {
            --bg: #07111d;
            --panel: #111827;
            --panel-soft: #0f172a;
            --line: rgba(148,163,184,.18);
            --text: #e5eefb;
            --muted: #9db0cc;
            --blue: #3b82f6;
            --green: #22c55e;
            --orange: #f59e0b;
            --red: #ef4444;
        }
        html, body, [data-testid="stAppViewContainer"] {
            background: linear-gradient(180deg, #07111d 0%, #0c1728 100%);
            color: var(--text);
        }
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
        }
        .card {
            background: rgba(15,23,42,0.95);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 25px rgba(15,23,42,0.18);
        }
        div[data-testid="stMetric"] {
            background: rgba(15,23,42,0.9);
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: 12px 14px;
        }
        .alert-card {
            border-left: 5px solid;
            padding: 12px 14px;
            margin: 8px 0;
            border-radius: 10px;
            background: rgba(15,23,42,0.75);
            border-top: 1px solid rgba(148,163,184,.12);
            border-right: 1px solid rgba(148,163,184,.12);
            border-bottom: 1px solid rgba(148,163,184,.12);
        }
        .alert-card small { opacity: .8; }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 999px;
            background: rgba(59,130,246,0.12);
            color: #cfe2ff;
            border: 1px solid rgba(59,130,246,0.2);
            font-size: 11px;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .small-muted { color: var(--muted); }
    </style>
    """,
    unsafe_allow_html=True,
)

app_summary = E.get_global_overview()
india_summary = E.get_india_monitoring()
news_items = E.get_news_feed()

with st.sidebar:
    st.title("POWERGUARD GLOBAL")
    st.caption("Energy Intelligence Platform")
    page = st.radio(
        "Navigation",
        [
            "Overview",
            "India Monitoring",
            "Theft Detection",
            "Data Centre",
            "News Intelligence",
            "Reports",
        ],
    )
    st.divider()
    st.caption("Data note: demo and public reference values are shown unless live utility integration is connected.")

# Shared utility / simulation input
with st.sidebar:
    st.subheader("Data Source")
    source = st.radio("Use", ["Simulated meter data", "Upload CSV", "Saved database"], label_visibility="collapsed")

    if source == "Simulated meter data":
        n_cons = st.slider("Consumers", 10, 100, 30, 5)
        n_days = st.slider("Days", 7, 60, 14)
        seed = st.number_input("Random seed", 0, 9999, 42)
        raw, truth = E.make_demo_data(n_cons, n_days, int(seed))
    elif source == "Upload CSV":
        st.caption("Columns: day, consumer_id, expected_kwh, meter_kwh (optional: category)")
        up = st.file_uploader("CSV file", type="csv")
        if up is None:
            st.info("Upload a CSV in the sidebar, or switch to Simulated meter data.")
            st.stop()
        raw, truth = pd.read_csv(up), None
    else:
        raw, truth = E.load_from_db(), None
        if raw is None:
            st.info("No saved data yet. Analyse some data first and press Save to database in the Reports page.")
            st.stop()

    st.subheader("Detection")
    threshold = st.slider("Deviation threshold (%)", 5, 60, 25)
    contamination = st.slider("ML sensitivity", 0.01, 0.15, 0.04, 0.01)
    tech_loss = st.slider("Technical loss (%)", 0.0, 20.0, 6.0, 0.5)
    tolerance = st.slider("Energy-balance tolerance (%)", 0.5, 10.0, 3.0, 0.5)
    override = st.number_input("Feeder supply override (kWh/day, 0 = use data)", 0.0, 1e7, 0.0, 100.0)

@st.cache_data(show_spinner="Analysing readings…")
def run(raw_df, threshold, contamination, tech_loss, tolerance, override):
    clean, errors, dropped = E.validate(raw_df)
    if errors:
        return None, None, errors, dropped
    a = E.analyse(clean, threshold, contamination)
    b = E.feeder_balance(a, tech_loss, tolerance, override or None)
    return a, b, [], dropped

analysed, balance, errors, dropped = run(raw, threshold, contamination, tech_loss, tolerance, override)
if errors:
    for e in errors:
        st.error(e)
    st.stop()
if dropped:
    st.warning(f"{dropped} invalid row(s) were excluded during validation.")

alerts = analysed[analysed["flagged"]].copy()
days = sorted(analysed["day"].unique())


def plot_style(fig, h=380):
    fig.update_layout(
        height=h,
        margin=dict(l=8, r=8, t=40, b=8),
        legend=dict(orientation="h", y=-0.2),
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e5eefb"),
    )
    return fig


if page == "Overview":
    st.title("POWERGUARD GLOBAL")
    st.caption("Smart Electricity Theft Detection & Energy Intelligence Platform")
    st.markdown('<div class="badge">Simulated / public reference data only</div>', unsafe_allow_html=True)

    st.subheader("Global overview")
    c = st.columns(5)
    c[0].metric("Total demand", f"{app_summary['consumption_total']:,.0f} GWh")
    c[1].metric("Distribution losses", f"{app_summary['loss_total']:,.0f} GWh")
    c[2].metric("Suspicious activity", f"{app_summary['suspicious_total']:,}")
    c[3].metric("Regional alerts", f"{app_summary['alert_total']:,}")
    c[4].metric("Coverage", app_summary["coverage"])

    st.subheader("Regional performance")
    reg_df = app_summary["regions"]
    fig = px.bar(
        reg_df,
        x="region",
        y="loss_pct",
        color="loss_pct",
        color_continuous_scale="RdYlGn_r",
        title="Regional loss exposure (%)",
    )
    st.plotly_chart(plot_style(fig, 400), use_container_width=True)

    left, right = st.columns(2)
    with left:
        geo = app_summary["countries"]
        fig = px.bar(
            geo,
            x="country",
            y="consumption_gwh",
            color="country",
            title="Electricity consumption by country",
        )
        st.plotly_chart(plot_style(fig, 400), use_container_width=True)
    with right:
        fig = px.pie(
            geo,
            names="country",
            values="loss_gwh",
            title="Loss contribution by country",
        )
        st.plotly_chart(plot_style(fig, 400), use_container_width=True)

    st.subheader("Live monitoring interface")
    st.caption("This section is designed for connected utility feeds, public datasets and validated meter imports. Current display uses simulated data when live sources are unavailable.")
    live = app_summary["live_feed"]
    st.dataframe(live, hide_index=True, use_container_width=True)

elif page == "India Monitoring":
    st.title("India Electricity Monitoring")
    st.caption("Public reference model for UHBVN, DHBVN and compatible future utilities.")
    utility = st.selectbox("Utility / region", [u["name"] for u in india_summary["utilities"]])
    util = next(u for u in india_summary["utilities"] if u["name"] == utility)

    c = st.columns(4)
    c[0].metric("Consumption", f"{util['consumption_gwh']:,.0f} GWh")
    c[1].metric("Losses", f"{util['loss_gwh']:,.0f} GWh")
    c[2].metric("Suspicious meters", f"{util['suspicious']:,.0f}")
    c[3].metric("System status", util["status"])

    st.subheader("Utility comparison")
    util_df = pd.DataFrame(india_summary["utilities"])
    fig = px.bar(
        util_df,
        x="name",
        y="loss_gwh",
        color="loss_gwh",
        title="Losses by Indian utility",
    )
    st.plotly_chart(plot_style(fig, 350), use_container_width=True)

    st.subheader("Regional monitoring")
    for item in india_summary["utilities"]:
        with st.expander(item["name"]):
            st.markdown(f"**Region:** {item['region']}  ")
            st.markdown(f"**Data source:** {item['source']}  ")
            st.markdown(f"**Connection status:** {item['connection']}  ")
            st.markdown(f"**Verified notes:** {item['notes']}  ")
            st.progress(float(item["risk_score"]), text=f"Risk score: {item['risk_score']}%")

elif page == "Theft Detection":
    st.title("Theft Detection")
    st.caption("Candidate anomalies are reviewed as potential issues, not proof of theft.")

    c = st.columns(4)
    c[0].metric("Readings analysed", f"{len(analysed):,}")
    c[1].metric("Flagged", f"{len(alerts)}", f"{len(alerts) / len(analysed) * 100:.1f}%", delta_color="off")
    c[2].metric("Rule + ML agree", int((alerts.detected_by == "Rule + ML").sum()))
    c[3].metric("Consumers involved", alerts.consumer_id.nunique())

    fig = px.scatter(
        analysed,
        x="expected_kwh",
        y="meter_kwh",
        color=analysed["flagged"].map({True: "Flagged", False: "Normal"}),
        color_discrete_map={"Flagged": RED, "Normal": BLUE},
        opacity=0.7,
        hover_data=["consumer_id", "day", "deviation_pct", "reason"],
        title="Expected vs recorded consumption",
    )
    mx = max(analysed.expected_kwh.max(), analysed.meter_kwh.max())
    fig.add_scatter(x=[0, mx], y=[0, mx], mode="lines", name="Meter = expected", line=dict(color=GREY, dash="dash"))
    fig.add_scatter(x=[0, mx], y=[0, mx * (1 - threshold / 100)], mode="lines", name=f"-{threshold}% threshold",
                    line=dict(color=ORANGE, dash="dot"))
    st.plotly_chart(plot_style(fig, 420), use_container_width=True)

    st.subheader("Detected readings")
    st.dataframe(
        alerts[["day", "consumer_id", "category", "expected_kwh", "meter_kwh", "deviation_pct",
                "severity", "detected_by", "reason"]]
        .sort_values("deviation_pct", ascending=False),
        hide_index=True,
        use_container_width=True,
    )

    if truth is not None and len(truth):
        with st.expander("Check against simulation scenarios"):
            m = analysed.merge(truth, on=["day", "consumer_id"], how="left")
            st.dataframe(
                m.groupby(m.kind.fillna("normal")).agg(
                    readings=("flagged", "size"), flagged=("flagged", "sum")
                ).assign(detection_rate=lambda d: (d.flagged / d.readings * 100).round(1)),
                use_container_width=True,
            )

elif page == "Data Centre":
    st.title("Global Data Centre")
    st.caption("CSV and public reference datasets are validated before analysis. Live utility integration is labelled and isolated.")

    st.subheader("Data quality overview")
    q = E.data_quality_snapshot(raw)
    c = st.columns(4)
    c[0].metric("Rows loaded", q["rows_total"])
    c[1].metric("Valid rows", q["rows_valid"])
    c[2].metric("Missing values", q["missing_cells"])
    c[3].metric("Duplicate rows", q["duplicate_rows"])

    st.subheader("Uploaded / loaded dataset")
    st.dataframe(raw.head(20), use_container_width=True)

    st.subheader("Data source / ingestion status")
    src = E.data_source_catalog()
    st.dataframe(pd.DataFrame(src), hide_index=True, use_container_width=True)

    if st.button("Save current readings and alerts to SQLite"):
        E.save_to_db(
            analysed[["day", "consumer_id", "category", "expected_kwh", "meter_kwh"]],
            alerts[["day", "consumer_id", "category", "expected_kwh", "meter_kwh", "deviation_pct",
                    "severity", "detected_by", "reason"]],
            E.DB_PATH,
        )
        st.success(f"Saved to {E.DB_PATH.name}.")

elif page == "News Intelligence":
    st.title("News and Intelligence Centre")
    st.caption("Verified sources and public utility updates only. No fabricated incidents are published.")

    for item in news_items:
        with st.container():
            st.markdown(
                f"<div class='card'>"
                f"<div class='badge'>{item['verification']}</div><br>"
                f"<h4>{item['headline']}</h4>"
                f"<div class='small-muted'>{item['source']} · {item['date']} · {item['location']}</div><br>"
                f"{item['summary']}"
                f"</div>",
                unsafe_allow_html=True,
            )

elif page == "Reports":
    st.title("PowerGuard Reports")
    st.caption("Download suspicious records and data summaries. These are investigations, not legal proof of theft.")

    sev_sel = st.multiselect("Include severities", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    rep = alerts[alerts.severity.isin(sev_sel)]
    c = st.columns(3)
    c[0].metric("Rows in report", len(rep))
    c[1].metric("Consumers", rep.consumer_id.nunique())
    c[2].metric("Period", f"{pd.Timestamp(days[0]):%d %b} – {pd.Timestamp(days[-1]):%d %b}")

    if rep.empty:
        st.info("No export rows available with the current filters.")
    else:
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇ Download CSV", E.alerts_to_csv(rep), "anomaly_report.csv", "text/csv", use_container_width=True)
        d2.download_button(
            "⬇ Download PDF",
            E.alerts_to_pdf(rep, balance, {"threshold": threshold, "tech_loss": tech_loss}),
            "anomaly_report.pdf",
            "application/pdf",
            use_container_width=True,
        )
        d3.download_button("⬇ Full analysed data", analysed.to_csv(index=False).encode(), "analysed_readings.csv", "text/csv", use_container_width=True)

        st.dataframe(rep[["day", "consumer_id", "category", "expected_kwh", "meter_kwh", "deviation_pct",
                          "severity", "detected_by", "reason"]], hide_index=True, use_container_width=True)

st.markdown("<hr style='border: 1px solid rgba(148,163,184,.15); margin-top: 1.5rem;'>", unsafe_allow_html=True)
