"""
Management dashboard for historical solar analysis and planning.

Public portfolio version:
- Generic branding
- Secrets loaded via Streamlit secrets.toml
- Cached database reads
- Clear function boundaries
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from mysql.connector import connect
from streamlit_autorefresh import st_autorefresh


APP_TITLE = "Solar Management Dashboard"
APP_SUBTITLE = "Historical analysis, planning, and comparison"
REFRESH_INTERVAL_MS = 300_000


st.set_page_config(page_title=APP_TITLE, layout="wide")
st.title(f"📊 {APP_TITLE}")
st.caption(APP_SUBTITLE)

st_autorefresh(interval=REFRESH_INTERVAL_MS, key="management_dashboard_refresh")


def get_mysql_connection():
    """Create a MySQL connection using Streamlit secrets."""
    return connect(
        host=st.secrets["mysql"]["host"],
        port=st.secrets["mysql"]["port"],
        database=st.secrets["mysql"]["database"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
    )


@st.cache_data(ttl=300, show_spinner=False)
def load_historical_data(start_date, end_date) -> pd.DataFrame:
    """Load historical energy and weather data within the selected range."""
    query = """
        SELECT
            TIME_LOCAL,
            Total_Power_W,
            Avg_Voltage_V,
            Avg_PF,
            Solar_Radiation,
            Cloud_Cover,
            Wind_Speed
        FROM energy_weather_data
        WHERE DATE(TIME_LOCAL) BETWEEN %s AND %s
        ORDER BY TIME_LOCAL ASC
    """

    conn = get_mysql_connection()
    try:
        df = pd.read_sql(query, conn, params=(start_date, end_date))
    finally:
        conn.close()

    if not df.empty:
        df["TIME_LOCAL"] = pd.to_datetime(df["TIME_LOCAL"])
        df["Date"] = df["TIME_LOCAL"].dt.date
        df["Hour"] = df["TIME_LOCAL"].dt.hour

    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_forecast_data() -> pd.DataFrame:
    """Load future weather forecast data."""
    query = """
        SELECT
            Forecast_Time,
            Retrieved_At,
            Solar_Radiation,
            Cloud_Cover,
            Temperature_C,
            Wind_Speed
        FROM weather_forecast_data
        WHERE Forecast_Time >= NOW()
        ORDER BY Forecast_Time ASC
    """

    conn = get_mysql_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    if not df.empty:
        df["Forecast_Time"] = pd.to_datetime(df["Forecast_Time"])
        df["Retrieved_At"] = pd.to_datetime(df["Retrieved_At"])
        df["Date"] = df["Forecast_Time"].dt.date
        df["Hour"] = df["Forecast_Time"].dt.hour

    return df


def aggregate_data(df: pd.DataFrame, level: str) -> pd.DataFrame:
    """Aggregate raw data to hourly or daily level."""
    if df.empty:
        return df.copy()

    temp = df.copy()

    if level == "Raw":
        return temp

    if level == "Hourly":
        temp["Bucket"] = temp["TIME_LOCAL"].dt.floor("h")
    elif level == "Daily":
        temp["Bucket"] = temp["TIME_LOCAL"].dt.floor("D")
    else:
        return temp

    grouped = (
        temp.groupby("Bucket", as_index=False)
        .agg(
            {
                "Total_Power_W": "mean",
                "Solar_Radiation": "mean",
                "Cloud_Cover": "mean",
                "Avg_Voltage_V": "mean",
                "Avg_PF": "mean",
                "Wind_Speed": "mean",
            }
        )
        .rename(columns={"Bucket": "TIME_LOCAL"})
    )
    grouped["Date"] = grouped["TIME_LOCAL"].dt.date
    grouped["Hour"] = grouped["TIME_LOCAL"].dt.hour
    return grouped


def calculate_kpis(df: pd.DataFrame) -> dict:
    """Calculate dashboard KPI values."""
    if df.empty:
        return {
            "total_power_sum": 0.0,
            "peak_power": 0.0,
            "avg_solar": 0.0,
            "avg_cloud": 0.0,
            "best_day": "N/A",
            "opportunity_score": 0.0,
        }

    daily_summary = (
        df.groupby("Date", as_index=False)
        .agg(
            {
                "Total_Power_W": "mean",
                "Solar_Radiation": "mean",
                "Cloud_Cover": "mean",
            }
        )
    )

    if not daily_summary.empty:
        daily_summary["Opportunity_Score"] = (
            daily_summary["Solar_Radiation"] * (100 - daily_summary["Cloud_Cover"]) / 100
        )
        best_day = (
            daily_summary.sort_values("Opportunity_Score", ascending=False)
            .iloc[0]["Date"]
        )
    else:
        best_day = "N/A"

    opportunity_score = (
        df["Solar_Radiation"] * (100 - df["Cloud_Cover"]) / 100
    ).mean()

    return {
        "total_power_sum": df["Total_Power_W"].sum(),
        "peak_power": df["Total_Power_W"].max(),
        "avg_solar": df["Solar_Radiation"].mean(),
        "avg_cloud": df["Cloud_Cover"].mean(),
        "best_day": str(best_day),
        "opportunity_score": opportunity_score,
    }


def production_day_label(avg_solar: float, avg_cloud: float) -> str:
    """Classify a day as Good, Moderate, or Poor."""
    if avg_solar >= 400 and avg_cloud <= 40:
        return "Good"
    if avg_solar >= 200 and avg_cloud <= 70:
        return "Moderate"
    return "Poor"


def build_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build a daily summary table."""
    if df.empty:
        return pd.DataFrame()

    summary = (
        df.groupby("Date", as_index=False)
        .agg(
            Peak_Power_W=("Total_Power_W", "max"),
            Avg_Solar_Radiation=("Solar_Radiation", "mean"),
            Avg_Cloud_Cover=("Cloud_Cover", "mean"),
        )
    )

    summary["Production_Suitability"] = summary.apply(
        lambda row: production_day_label(
            row["Avg_Solar_Radiation"], row["Avg_Cloud_Cover"]
        ),
        axis=1,
    )
    return summary


def build_forecast_day_labels(forecast_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate forecast into daily labels."""
    if forecast_df.empty:
        return pd.DataFrame()

    daily = (
        forecast_df.groupby("Date", as_index=False)
        .agg({"Solar_Radiation": "mean", "Cloud_Cover": "mean"})
    )
    daily["Day_Label"] = daily.apply(
        lambda row: production_day_label(row["Solar_Radiation"], row["Cloud_Cover"]),
        axis=1,
    )
    return daily


def compare_selected_days(
    df: pd.DataFrame, date1, date2, metric: str
) -> pd.DataFrame:
    """Build a normalized same-time comparison between two days."""
    if df.empty:
        return pd.DataFrame()

    temp = df.copy()
    temp["TimeOnly"] = temp["TIME_LOCAL"].dt.strftime("%H:%M")

    compare_df = temp[temp["Date"].isin([date1, date2])].copy()
    compare_df["Compare_Label"] = compare_df["Date"].astype(str)

    return compare_df[["TimeOnly", metric, "Compare_Label"]]


def main() -> None:
    """Run the management dashboard."""
    st.sidebar.header("Filters")

    default_end = pd.Timestamp.today().date()
    default_start = default_end - pd.Timedelta(days=6)

    date_range = st.sidebar.date_input("Date range", value=(default_start, default_end))

    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date = default_start
        end_date = default_end

    aggregation_level = st.sidebar.selectbox(
        "Aggregation level", ["Raw", "Hourly", "Daily"], index=1
    )

    metric_selector = st.sidebar.selectbox(
        "Primary metric", ["Total_Power_W", "Solar_Radiation", "Cloud_Cover"], index=0
    )

    comparison_mode = st.sidebar.selectbox(
        "Comparison mode", ["None", "Compare Days", "Compare Periods"], index=0
    )

    hist_df = load_historical_data(start_date, end_date)
    forecast_df = load_forecast_data()

    if hist_df.empty:
        st.warning("No historical data found for selected range.")
        st.stop()

    agg_df = aggregate_data(hist_df, aggregation_level)
    kpis = calculate_kpis(hist_df)
    summary_table = build_summary_table(hist_df)
    forecast_labels_df = build_forecast_day_labels(forecast_df)

    st.subheader("Management KPIs")

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.metric("Total Power Sum", f"{kpis['total_power_sum']:.0f}")
    with k2:
        st.metric("Peak Power (W)", f"{kpis['peak_power']:.0f}")
    with k3:
        st.metric("Avg Solar Radiation", f"{kpis['avg_solar']:.1f}")
    with k4:
        st.metric("Avg Cloud Cover (%)", f"{kpis['avg_cloud']:.1f}")
    with k5:
        st.metric("Best Production Day", kpis["best_day"])
    with k6:
        st.metric("Opportunity Score", f"{kpis['opportunity_score']:.1f}")

    st.subheader("Historical Trends")

    trend_col1, trend_col2 = st.columns(2)

    with trend_col1:
        fig_metric = px.line(
            agg_df,
            x="TIME_LOCAL",
            y=metric_selector,
            title=f"{metric_selector} Over Time",
        )
        st.plotly_chart(fig_metric, use_container_width=True)

    with trend_col2:
        fig_combined = go.Figure()
        fig_combined.add_trace(
            go.Scatter(x=agg_df["TIME_LOCAL"], y=agg_df["Total_Power_W"], mode="lines", name="Power")
        )
        fig_combined.add_trace(
            go.Scatter(x=agg_df["TIME_LOCAL"], y=agg_df["Solar_Radiation"], mode="lines", name="Solar Radiation")
        )
        fig_combined.add_trace(
            go.Scatter(x=agg_df["TIME_LOCAL"], y=agg_df["Cloud_Cover"], mode="lines", name="Cloud Cover")
        )
        fig_combined.update_layout(title="Power + Solar + Cloud")
        st.plotly_chart(fig_combined, use_container_width=True)

    st.subheader("Solar + Weather Relationship Analysis")

    rel1, rel2 = st.columns(2)

    with rel1:
        fig_scatter_solar = px.scatter(
            hist_df,
            x="Solar_Radiation",
            y="Total_Power_W",
            color="Cloud_Cover",
            title="Power vs Solar Radiation",
        )
        st.plotly_chart(fig_scatter_solar, use_container_width=True)

    with rel2:
        fig_scatter_cloud = px.scatter(
            hist_df,
            x="Cloud_Cover",
            y="Total_Power_W",
            color="Solar_Radiation",
            title="Power vs Cloud Cover",
        )
        st.plotly_chart(fig_scatter_cloud, use_container_width=True)

    st.subheader("3-Day Forecast Planning")

    forecast_col1, forecast_col2 = st.columns([2, 1])

    with forecast_col1:
        if forecast_df.empty:
            st.warning("No forecast data found.")
        else:
            fig_forecast = go.Figure()
            fig_forecast.add_trace(
                go.Scatter(
                    x=forecast_df["Forecast_Time"],
                    y=forecast_df["Solar_Radiation"],
                    mode="lines",
                    name="Solar Radiation",
                )
            )
            fig_forecast.add_trace(
                go.Scatter(
                    x=forecast_df["Forecast_Time"],
                    y=forecast_df["Cloud_Cover"],
                    mode="lines",
                    name="Cloud Cover",
                )
            )
            fig_forecast.update_layout(title="Forecast: Solar Radiation + Cloud Cover")
            st.plotly_chart(fig_forecast, use_container_width=True)

    with forecast_col2:
        if forecast_labels_df.empty:
            st.info("No forecast summary available.")
        else:
            st.markdown("**Day Quality**")
            for _, row in forecast_labels_df.iterrows():
                st.write(f"{row['Date']}: {row['Day_Label']}")

    st.subheader("Comparison / Drill-down")

    if comparison_mode == "Compare Days":
        unique_dates = sorted(hist_df["Date"].unique())

        if len(unique_dates) >= 2:
            c1, c2 = st.columns(2)

            with c1:
                compare_day_1 = st.selectbox(
                    "Select Day 1", unique_dates, index=max(0, len(unique_dates) - 2)
                )

            with c2:
                compare_day_2 = st.selectbox(
                    "Select Day 2", unique_dates, index=max(0, len(unique_dates) - 1)
                )

            compare_df = compare_selected_days(
                hist_df, compare_day_1, compare_day_2, metric_selector
            )

            if not compare_df.empty:
                fig_compare = px.line(
                    compare_df,
                    x="TimeOnly",
                    y=metric_selector,
                    color="Compare_Label",
                    title=f"Compare Days: {compare_day_1} vs {compare_day_2}",
                )
                st.plotly_chart(fig_compare, use_container_width=True)

    elif comparison_mode == "Compare Periods":
        st.info("Period comparison can be added next by selecting two custom date ranges.")
    else:
        st.info("Select a comparison mode in the sidebar to compare days or periods.")

    st.subheader("Daily Summary Table")

    if summary_table.empty:
        st.info("No summary data available.")
    else:
        st.dataframe(summary_table, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
