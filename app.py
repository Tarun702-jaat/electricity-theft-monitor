import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import engine as E

st.set_page_config(page_title="Electricity Theft Monitor", page_icon="⚡", layout="wide")

BLUE, ORANGE, RED, GREEN, GREY = "#2563eb", "#f59e0b", "#dc2626", "#16a34a", "#94a3b8"
SEV_COLOR = {"High": RED, "Medium": ORANGE, "Low": "#eab308", "Normal": GREEN}

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem;}
      div[data-testid="stMetric"] {background: rgba(148,163,184,.12); padding: 14px 16px;
                                    border-radius: 12px; border: 1px solid rgba(148,163,184,.25);}
      .alert-card {border-left: 5px solid; padding: 10px 14px; margin: 6px 0; border-radius: 8px;
                   background: rgba(148,163,184,.10);}
      .alert-card small {opacity: .75;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Sidebar
st.sidebar.title("⚡ Theft Monitor")
page = st.sidebar.radio(
    "Section",
    ["Dashboard", "Consumer Monitoring", "Theft Detection", "Live Alerts", "Analytics", "Reports"],
)

st.sidebar.divider()
st.sidebar.subheader("Data source")
source = st.sidebar.radio("Use", ["Simulated meter data", "Upload CSV", "Saved database"], label_visibility="collapsed")

if source == "Simulated meter data":
    n_cons = st.sidebar.slider("Consumers", 10, 100, 30, 5)
    n_days = st.sidebar.slider("Days", 7, 60, 14)
    seed = st.sidebar.number_input("Random seed", 0, 9999, 42)
    raw, truth = E.make_demo_data(n_cons, n_days, int(seed))
elif source == "Upload CSV":
    st.sidebar.caption("Columns: day, consumer_id, expected_kwh, meter_kwh (optional: category)")
    up = st.sidebar.file_uploader("CSV file", type="csv")
    if up is None:
        st.info("Upload a CSV in the sidebar, or switch to *Simulated meter data*.")
        st.stop()
    raw, truth = pd.read_csv(up), None
else:
    raw, truth = E.load_from_db(), None
    if raw is None:
        st.info("No saved data yet. Analyse some data first and press **Save to database** on the Reports page.")
        st.stop()

st.sidebar.subheader("Detection settings")
threshold = st.sidebar.slider("Deviation threshold (%)", 5, 60, 25,
                              help="Flag a reading when it differs from the reference by at least this much.")
contamination = st.sidebar.slider("ML sensitivity", 0.01, 0.15, 0.04, 0.01,
                                  help="Expected share of unusual readings for the Isolation Forest model.")
tech_loss = st.sidebar.slider("Technical loss (%)", 0.0, 20.0, 6.0, 0.5,
                              help="Expected line / transformer losses.")
tolerance = st.sidebar.slider("Energy-balance tolerance (%)", 0.5, 10.0, 3.0, 0.5,
                              help="Unexplained loss above this share of supply raises a warning.")
override = st.sidebar.number_input("Feeder supply override (kWh/day, 0 = use data)", 0.0, 1e7, 0.0, 100.0)

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
    st.warning(f"{dropped} invalid row(s) (missing, non-numeric or negative values) were excluded.")

alerts = analysed[analysed["flagged"]].copy()
days = sorted(analysed["day"].unique())

st.sidebar.divider()
st.sidebar.caption("Alerts are decision-support only. They do **not** prove theft; "
                   "each needs authorised verification (meter fault, missing data and "
                   "wrong loss estimates must be ruled out).")


def plot_style(fig, h=380):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.2),
                      hovermode="x unified")
    return fig


# 1 Dashboard
if page == "Dashboard":
    st.title("Dashboard")
    sup, rec = balance["supplied_kwh"].sum(), balance["recorded_kwh"].sum()
    tl, unx = balance["tech_loss_kwh"].sum(), balance["unexplained_kwh"].sum()
    st.caption(f"{len(days)} days · {analysed.consumer_id.nunique()} consumers · "
               f"{pd.Timestamp(days[0]):%d %b} – {pd.Timestamp(days[-1]):%d %b %Y}")

    c = st.columns(5)
    c[0].metric("Electricity supplied", f"{sup:,.0f} kWh")
    c[1].metric("Recorded consumption", f"{rec:,.0f} kWh")
    c[2].metric("Estimated total loss", f"{sup - rec:,.0f} kWh", f"{(sup - rec) / sup * 100:.1f}% of supply",
                delta_color="off")
    c[3].metric("Unexplained loss", f"{unx:,.0f} kWh", f"{unx / sup * 100:.1f}% of supply",
                delta_color="inverse")
    c[4].metric("Alerts raised", f"{len(alerts)}", f"{(alerts.severity == 'High').sum()} high severity",
                delta_color="off")

    latest = balance.iloc[-1]
    if latest.warning:
        st.error(f"⚠ Energy-accounting warning on {pd.Timestamp(latest.day):%d %b}: "
                 f"{latest.unexplained_kwh:,.0f} kWh ({latest.unexplained_pct:.1f}%) of supply is unexplained "
                 f"(tolerance {tolerance}%). Review for theft, meter faults, timing mismatch or a wrong loss estimate.")
    else:
        st.success(f"Energy balance on {pd.Timestamp(latest.day):%d %b} is within tolerance "
                   f"({latest.unexplained_pct:.1f}% unexplained).")

    left, right = st.columns([3, 2])
    with left:
        fig = go.Figure()
        fig.add_bar(x=balance.day, y=balance.recorded_kwh, name="Recorded", marker_color=BLUE)
        fig.add_bar(x=balance.day, y=balance.tech_loss_kwh, name="Technical loss", marker_color=GREY)
        fig.add_bar(x=balance.day, y=balance.unexplained_kwh.clip(lower=0), name="Unexplained", marker_color=RED)
        fig.add_scatter(x=balance.day, y=balance.supplied_kwh, name="Supplied", mode="lines+markers",
                        line=dict(color="#111827", width=2))
        fig.update_layout(barmode="stack", title="Where the supplied energy went (kWh per day)")
        st.plotly_chart(plot_style(fig), use_container_width=True)
    with right:
        sev = alerts["severity"].value_counts().reindex(["High", "Medium", "Low"]).dropna().reset_index()
        sev.columns = ["severity", "count"]
        if len(sev):
            fig = px.pie(sev, names="severity", values="count", hole=0.55, color="severity",
                         color_discrete_map=SEV_COLOR, title="Alerts by severity")
            st.plotly_chart(plot_style(fig), use_container_width=True)
        else:
            st.info("No alerts at the current settings.")

    st.subheader("Highest-priority consumers")
    cs = E.consumer_summary(analysed).sort_values("flagged_days", ascending=False).head(5)
    st.dataframe(cs, hide_index=True, use_container_width=True)

# 2 Consumer Monitoring
elif page == "Consumer Monitoring":
    st.title("Consumer Monitoring")
    cs = E.consumer_summary(analysed)
    f1, f2, f3 = st.columns(3)
    cat = f1.multiselect("Category", sorted(cs.category.unique()), default=sorted(cs.category.unique()))
    risk = f2.multiselect("Status", ["Normal", "Watch", "Priority review"], default=["Normal", "Watch", "Priority review"])
    q = f3.text_input("Search consumer ID")
    view = cs[cs.category.isin(cat) & cs.risk.isin(risk)]
    if q:
        view = view[view.consumer_id.str.contains(q, case=False)]
    st.dataframe(
        view, hide_index=True, use_container_width=True,
        column_config={
            "avg_deviation_pct": st.column_config.NumberColumn("Avg deviation %", format="%.1f"),
            "flagged_days": st.column_config.ProgressColumn("Flagged days", min_value=0,
                                                            max_value=max(1, int(cs.flagged_days.max())), format="%d"),
        },
    )

    st.subheader("Meter readings for one consumer")
    cid = st.selectbox("Consumer", view.consumer_id.tolist() or cs.consumer_id.tolist())
    one = analysed[analysed.consumer_id == cid]
    fig = go.Figure()
    fig.add_scatter(x=one.day, y=one.expected_kwh, name="Expected (reference)", line=dict(color=GREY, dash="dash"))
    fig.add_scatter(x=one.day, y=one.meter_kwh, name="Meter reading", mode="lines+markers", line=dict(color=BLUE))
    fl = one[one.flagged]
    fig.add_scatter(x=fl.day, y=fl.meter_kwh, name="Flagged", mode="markers",
                    marker=dict(color=RED, size=12, symbol="x"), text=fl.reason,
                    hovertemplate="%{text}<extra></extra>")
    fig.update_layout(title=f"{cid} – daily kWh", yaxis_title="kWh")
    st.plotly_chart(plot_style(fig), use_container_width=True)
    st.dataframe(one[["day", "expected_kwh", "meter_kwh", "deviation_pct", "severity", "reason"]]
                 .sort_values("day", ascending=False), hide_index=True, use_container_width=True)

# 3 Theft Detection
elif page == "Theft Detection":
    st.title("Theft Detection")
    st.caption("Two detectors run together: a **rule** (reading differs from reference by the threshold) and an "
               "**Isolation Forest** model (reading unusual compared with the consumer's own history). "
               "A flagged reading is a *candidate for verification*, not a finding of theft.")

    c = st.columns(4)
    c[0].metric("Readings analysed", f"{len(analysed):,}")
    c[1].metric("Flagged", f"{len(alerts)}", f"{len(alerts) / len(analysed) * 100:.1f}%", delta_color="off")
    c[2].metric("Rule + ML agree", int((alerts.detected_by == "Rule + ML").sum()))
    c[3].metric("Consumers involved", alerts.consumer_id.nunique())

    fig = px.scatter(
        analysed, x="expected_kwh", y="meter_kwh",
        color=analysed["flagged"].map({True: "Flagged", False: "Normal"}),
        color_discrete_map={"Flagged": RED, "Normal": BLUE},
        opacity=0.7,
        hover_data=["consumer_id", "day", "deviation_pct", "reason"],
        title="Expected vs recorded (points far below the diagonal read low)",
    )
    mx = max(analysed.expected_kwh.max(), analysed.meter_kwh.max())
    fig.add_scatter(x=[0, mx], y=[0, mx], mode="lines", name="Meter = expected", line=dict(color=GREY, dash="dash"))
    fig.add_scatter(x=[0, mx], y=[0, mx * (1 - threshold / 100)], mode="lines", name=f"-{threshold}% threshold",
                    line=dict(color=ORANGE, dash="dot"))
    st.plotly_chart(plot_style(fig, 440), use_container_width=True)

    left, right = st.columns(2)
    with left:
        fig = px.histogram(analysed, x="deviation_pct", nbins=50, title="Distribution of deviation %",
                           color_discrete_sequence=[BLUE])
        fig.add_vline(x=threshold, line_color=RED, line_dash="dash")
        fig.add_vline(x=-threshold, line_color=RED, line_dash="dash")
        st.plotly_chart(plot_style(fig, 320), use_container_width=True)
    with right:
        top = (alerts.groupby("consumer_id").agg(flagged_days=("flagged", "sum"),
                                                 avg_dev=("deviation_pct", "mean"))
               .sort_values("flagged_days", ascending=False).head(10).reset_index())
        fig = px.bar(top, x="flagged_days", y="consumer_id", orientation="h", title="Most-flagged consumers",
                     color_discrete_sequence=[RED])
        fig.update_layout(yaxis=dict(autorange="reversed"))
        st.plotly_chart(plot_style(fig, 320), use_container_width=True)

    st.subheader("Detected readings")
    st.dataframe(alerts[["day", "consumer_id", "expected_kwh", "meter_kwh", "deviation_pct",
                         "anomaly_score", "severity", "detected_by", "reason"]]
                 .sort_values("anomaly_score", ascending=False),
                 hide_index=True, use_container_width=True)

# 4 Live Alerts
elif page == "Live Alerts":
    st.title("Live Alerts")
    st.caption("Replays the readings day by day as if meters were reporting in. Alerts are for verification only.")

    if "cursor" not in st.session_state or st.session_state.cursor >= len(days):
        st.session_state.cursor = min(len(days) - 1, max(0, len(days) - 3))

    b1, b2, b3, b4 = st.columns([1, 1, 1, 2])
    if b1.button("▶ Next day", use_container_width=True):
        st.session_state.cursor = min(st.session_state.cursor + 1, len(days) - 1)
    if b2.button("↺ Restart", use_container_width=True):
        st.session_state.cursor = 0
    auto = b3.toggle("Auto-play", value=False)
    sev_f = b4.multiselect("Severity", ["High", "Medium", "Low"], default=["High", "Medium", "Low"],
                           label_visibility="collapsed")

    @st.fragment(run_every=1.5 if auto else None)
    def feed():
        if auto and st.session_state.cursor < len(days) - 1:
            st.session_state.cursor += 1
        cur = pd.Timestamp(days[st.session_state.cursor])
        st.progress((st.session_state.cursor + 1) / len(days), text=f"Reporting up to {cur:%d %b %Y}")
        seen = alerts[(alerts.day <= cur) & alerts.severity.isin(sev_f)].sort_values(["day", "anomaly_score"], ascending=False)
        today = seen[seen.day == cur]
        bal_today = balance[balance.day == cur].iloc[0]

        m = st.columns(3)
        m[0].metric("Alerts today", len(today))
        m[1].metric("Alerts so far", len(seen))
        m[2].metric("Unexplained today", f"{bal_today.unexplained_pct:.1f}%")
        if bal_today.warning:
            st.warning(f"Energy-accounting warning: {bal_today.unexplained_kwh:,.0f} kWh "
                       f"({bal_today.unexplained_pct:.1f}%) unexplained on {cur:%d %b}.")

        if seen.empty:
            st.success("No suspicious readings so far.")
        for r in seen.head(25).itertuples():
            colr = SEV_COLOR[r.severity]
            new = " 🆕" if r.day == cur else ""
            st.markdown(
                f'<div class="alert-card" style="border-color:{colr}">'
                f'<b style="color:{colr}">{r.severity.upper()}</b> · <b>{r.consumer_id}</b> '
                f'({r.category}){new}<br>{r.reason}<br>'
                f'<small>{r.day:%d %b %Y} · meter {r.meter_kwh:.1f} kWh vs expected {r.expected_kwh:.1f} kWh · '
                f'detected by {r.detected_by} · needs verification</small></div>',
                unsafe_allow_html=True)

    feed()

# 5 Analytics
elif page == "Analytics":
    st.title("Analytics")
    fig = go.Figure()
    fig.add_scatter(x=balance.day, y=balance.supplied_kwh, name="Supplied", line=dict(color="#111827", width=3))
    fig.add_scatter(x=balance.day, y=balance.recorded_kwh, name="Recorded", line=dict(color=BLUE, width=3),
                    fill="tonexty", fillcolor="rgba(220,38,38,.15)")
    fig.update_layout(title="Supplied vs recorded electricity (shaded gap = total loss)", yaxis_title="kWh")
    st.plotly_chart(plot_style(fig, 420), use_container_width=True)

    l, r = st.columns(2)
    with l:
        fig = go.Figure()
        fig.add_scatter(x=balance.day, y=balance.total_loss_pct, name="Total loss %", line=dict(color=ORANGE))
        fig.add_scatter(x=balance.day, y=balance.unexplained_pct, name="Unexplained %", line=dict(color=RED))
        fig.add_hline(y=tolerance, line_dash="dash", line_color=GREY, annotation_text="tolerance")
        fig.update_layout(title="Loss percentage per day", yaxis_title="% of supply")
        st.plotly_chart(plot_style(fig, 340), use_container_width=True)
    with r:
        by_cat = analysed.groupby("category")[["expected_kwh", "meter_kwh"]].sum().reset_index()
        fig = go.Figure()
        fig.add_bar(x=by_cat.category, y=by_cat.expected_kwh, name="Expected", marker_color=GREY)
        fig.add_bar(x=by_cat.category, y=by_cat.meter_kwh, name="Recorded", marker_color=BLUE)
        fig.update_layout(barmode="group", title="Expected vs recorded by category", yaxis_title="kWh")
        st.plotly_chart(plot_style(fig, 340), use_container_width=True)

    l, r = st.columns(2)
    with l:
        daily = alerts.groupby(["day", "severity"]).size().reset_index(name="alerts")
        fig = px.bar(daily, x="day", y="alerts", color="severity", color_discrete_map=SEV_COLOR,
                     title="Alerts per day")
        st.plotly_chart(plot_style(fig, 340), use_container_width=True)
    with r:
        pivot = analysed.pivot(index="consumer_id", columns="day", values="deviation_pct")
        if len(pivot) > 40:
            pivot = pivot.loc[pivot.abs().max(axis=1).sort_values(ascending=False).head(40).index]
        fig = px.imshow(pivot, aspect="auto", color_continuous_scale="RdBu_r", zmin=-60, zmax=60,
                        title="Deviation % heatmap (red = reads low)")
        st.plotly_chart(plot_style(fig, 340), use_container_width=True)

# 6 Reports
else:
    st.title("Reports")
    st.caption("Download the detected anomalies. Each row is a reading that needs authorised verification.")
    sev_sel = st.multiselect("Include severities", ["High", "Medium", "Low"], default=["High", "Medium", "Low"])
    rep = alerts[alerts.severity.isin(sev_sel)]
    c = st.columns(3)
    c[0].metric("Rows in report", len(rep))
    c[1].metric("Consumers", rep.consumer_id.nunique())
    c[2].metric("Period", f"{pd.Timestamp(days[0]):%d %b} – {pd.Timestamp(days[-1]):%d %b}")

    if rep.empty:
        st.info("Nothing to export at the current settings.")
    else:
        d1, d2, d3 = st.columns(3)
        d1.download_button("⬇ Download CSV", E.alerts_to_csv(rep), "anomaly_report.csv", "text/csv",
                           use_container_width=True)
        d2.download_button(
            "⬇ Download PDF",
            E.alerts_to_pdf(rep, balance, {"threshold": threshold, "tech_loss": tech_loss}),
            "anomaly_report.pdf", "application/pdf", use_container_width=True)
        d3.download_button("⬇ Full analysed data (CSV)", analysed.to_csv(index=False).encode(),
                           "analysed_readings.csv", "text/csv", use_container_width=True)
        st.dataframe(rep[["day", "consumer_id", "category", "expected_kwh", "meter_kwh", "deviation_pct",
                         "severity", "detected_by", "reason"]], hide_index=True, use_container_width=True)

    st.divider()
    if st.button("💾 Save readings and alerts to SQLite database"):
        E.save_to_db(
            analysed[["day", "consumer_id", "category", "expected_kwh", "meter_kwh"]],
            alerts[["day", "consumer_id", "category", "expected_kwh", "meter_kwh", "deviation_pct",
                    "severity", "detected_by", "reason"]],
            E.DB_PATH
        )
        st.success(f"Saved to {E.DB_PATH.name}. Choose *Saved database* as the data source to reload it.")
