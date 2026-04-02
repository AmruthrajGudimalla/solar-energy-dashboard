"""
Production dashboard for live solar monitoring.

Public portfolio version:
- Generic branding
- Secrets loaded via Streamlit secrets.toml
- Clear function boundaries
- Cached database reads
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from mysql.connector import connect
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh


# =========================================================
# APP CONFIGURATION
# =========================================================
APP_TITLE = "Production Solar Dashboard"
APP_SUBTITLE = "Live monitoring for power generation and short-term solar availability"

SYSTEM_CAPACITY_W = 20_000
SOLAR_RADIATION_MAX = 1_000
CLOUD_COVER_MAX = 100

LIVE_LOOKBACK_MINUTES = 120
ALERT_LOOKAHEAD_HOURS = 3
FORECAST_DAYS_TO_SHOW = 2

VERY_GOOD_SOLAR = 500
GOOD_SOLAR = 350
OKAY_SOLAR = 180

VERY_GOOD_CLOUD = 25
GOOD_CLOUD = 40
OKAY_CLOUD = 70

REFRESH_INTERVAL_MS = 60_000


# =========================================================
# STREAMLIT PAGE SETUP
# =========================================================
st.set_page_config(page_title=APP_TITLE, layout="wide")
st_autorefresh(interval=REFRESH_INTERVAL_MS, key="production_dashboard_refresh")

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2.2rem;
        padding-bottom: 0.4rem;
        max-width: 100%;
    }

    .main-title {
        font-size: 1.9rem;
        font-weight: 800;
        margin-bottom: 0.15rem;
    }

    .sub-title {
        font-size: 0.98rem;
        color: #6c757d;
        margin-bottom: 1.0rem;
    }

    .gauge-label {
        text-align: center;
        font-weight: 700;
        font-size: 1rem;
        margin-top: -4px;
        margin-bottom: 2px;
    }

    .next3h-card {
        border-radius: 18px;
        padding: 18px 16px;
        min-height: 105px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        text-align: center;
        font-weight: 700;
        box-shadow: 0 4px 14px rgba(0,0,0,0.18);
    }

    .rating-very-good {
        background: linear-gradient(135deg, #198754, #157347);
        color: white;
    }

    .rating-good {
        background: linear-gradient(135deg, #20c997, #0ca678);
        color: white;
    }

    .rating-okay {
        background: linear-gradient(135deg, #fd7e14, #e8590c);
        color: white;
    }

    .rating-poor {
        background: linear-gradient(135deg, #dc3545, #b02a37);
        color: white;
    }

    .next3h-title {
        font-size: 1rem;
        opacity: 0.95;
        margin-bottom: 8px;
    }

    .next3h-value {
        font-size: 2rem;
        line-height: 1.1;
        margin-bottom: 6px;
    }

    .next3h-sub {
        font-size: 0.95rem;
        opacity: 0.95;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DATABASE
# =========================================================
def get_mysql_connection():
    """Create a MySQL connection using Streamlit secrets."""
    return connect(
        host=st.secrets["mysql"]["host"],
        port=st.secrets["mysql"]["port"],
        database=st.secrets["mysql"]["database"],
        user=st.secrets["mysql"]["user"],
        password=st.secrets["mysql"]["password"],
    )


@st.cache_data(ttl=60, show_spinner=False)
def load_live_data(lookback_minutes: int) -> pd.DataFrame:
    """Load recent live energy and weather data."""
    query = f"""
        SELECT
            TIME_LOCAL,
            Total_Power_W,
            Solar_Radiation,
            Cloud_Cover
        FROM energy_weather_data
        WHERE TIME_LOCAL >= NOW() - INTERVAL {lookback_minutes} MINUTE
        ORDER BY TIME_LOCAL ASC
    """

    conn = get_mysql_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    if not df.empty:
        df["TIME_LOCAL"] = pd.to_datetime(df["TIME_LOCAL"])

    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_forecast_data() -> pd.DataFrame:
    """Load future forecast data."""
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

    return df


# =========================================================
# BUSINESS LOGIC
# =========================================================
def classify_next_3h(forecast_df: pd.DataFrame) -> tuple[str, str, str, str]:
    """Classify the next 3 hours of expected solar conditions."""
    if forecast_df.empty:
        return "NO DATA", "rating-okay", "⚠️", "No forecast available"

    now_ts = pd.Timestamp.now().floor("h")
    end_ts = now_ts + pd.Timedelta(hours=ALERT_LOOKAHEAD_HOURS)

    next_3h = forecast_df[
        (forecast_df["Forecast_Time"] >= now_ts)
        & (forecast_df["Forecast_Time"] < end_ts)
    ].copy()

    if next_3h.empty:
        return "NO DATA", "rating-okay", "⚠️", "No forecast available"

    avg_solar = next_3h["Solar_Radiation"].mean()
    avg_cloud = next_3h["Cloud_Cover"].mean()

    if avg_solar >= VERY_GOOD_SOLAR and avg_cloud <= VERY_GOOD_CLOUD:
        return "VERY GOOD", "rating-very-good", "☀️", "Strong solar availability expected"
    if avg_solar >= GOOD_SOLAR and avg_cloud <= GOOD_CLOUD:
        return "GOOD", "rating-good", "🌤️", "Favorable solar conditions expected"
    if avg_solar >= OKAY_SOLAR and avg_cloud <= OKAY_CLOUD:
        return "OKAY", "rating-okay", "⛅", "Usable but moderate conditions"
    return "POOR", "rating-poor", "☁️", "Weak solar conditions expected"


def filter_forecast_window(forecast_df: pd.DataFrame, days_to_show: int) -> pd.DataFrame:
    """Return only the forecast horizon to show on the dashboard."""
    if forecast_df.empty:
        return pd.DataFrame()

    now_ts = pd.Timestamp.now().floor("h")
    end_ts = now_ts + pd.Timedelta(days=days_to_show)

    return forecast_df[
        (forecast_df["Forecast_Time"] >= now_ts)
        & (forecast_df["Forecast_Time"] < end_ts)
    ].copy()


# =========================================================
# CHARTS
# =========================================================
def gauge_chart(value: float, max_value: float, suffix: str = "") -> go.Figure:
    """Build a gauge chart for one KPI."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=float(value) if pd.notna(value) else 0,
            number={"suffix": suffix},
            gauge={
                "axis": {"range": [0, max_value]},
                "bar": {"thickness": 0.34},
                "steps": [
                    {"range": [0, max_value * 0.4], "color": "rgba(220,53,69,0.35)"},
                    {"range": [max_value * 0.4, max_value * 0.7], "color": "rgba(253,126,20,0.35)"},
                    {"range": [max_value * 0.7, max_value], "color": "rgba(25,135,84,0.35)"},
                ],
            },
        )
    )
    fig.update_layout(height=200, margin=dict(l=8, r=8, t=10, b=0))
    return fig


def build_power_chart(live_df: pd.DataFrame) -> go.Figure:
    """Build the recent power trend chart."""
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=live_df["TIME_LOCAL"],
            y=live_df["Total_Power_W"],
            mode="lines",
            name="Power",
            line=dict(width=3),
        )
    )
    fig.update_layout(
        title="Power Utilization - Last 2 Hours",
        height=315,
        margin=dict(l=12, r=12, t=42, b=10),
        showlegend=False,
        xaxis_title="Time",
        yaxis_title="Power (W)",
    )
    return fig


def build_weather_forecast_chart(forecast_df: pd.DataFrame) -> go.Figure:
    """Build the forecast chart with solar radiation and cloud cover."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Scatter(
            x=forecast_df["Forecast_Time"],
            y=forecast_df["Solar_Radiation"],
            mode="lines",
            name="Solar Radiation",
            line=dict(width=3),
        ),
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=forecast_df["Forecast_Time"],
            y=forecast_df["Cloud_Cover"],
            mode="lines",
            name="Cloud Cover",
            line=dict(width=2, dash="dot"),
        ),
        secondary_y=True,
    )

    fig.update_yaxes(title_text="Solar Radiation", secondary_y=False)
    fig.update_yaxes(title_text="Cloud Cover (%)", range=[0, 100], secondary_y=True)
    fig.update_layout(
        title={"text": "Weather Forecast - Next 2 Days", "y": 0.95},
        height=315,
        margin=dict(l=12, r=12, t=70, b=10),
        showlegend=False,
    )
    return fig


# =========================================================
# APP RENDERING
# =========================================================
def main() -> None:
    """Run the dashboard."""
    live_df = load_live_data(LIVE_LOOKBACK_MINUTES)
    forecast_df = load_forecast_data()

    if live_df.empty:
        st.warning("No live data found.")
        st.stop()

    latest_live = live_df.iloc[-1]
    forecast_2d = filter_forecast_window(forecast_df, FORECAST_DAYS_TO_SHOW)
    rating_text, rating_class, rating_icon, rating_sub = classify_next_3h(forecast_df)

    st.markdown(f"<div class='main-title'>☀️ {APP_TITLE}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sub-title'>{APP_SUBTITLE}</div>", unsafe_allow_html=True)

    g1, g2, g3 = st.columns(3)

    with g1:
        st.plotly_chart(
            gauge_chart(latest_live["Total_Power_W"], SYSTEM_CAPACITY_W, " W"),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.markdown("<div class='gauge-label'>Current Power</div>", unsafe_allow_html=True)

    with g2:
        st.plotly_chart(
            gauge_chart(latest_live["Solar_Radiation"], SOLAR_RADIATION_MAX),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.markdown("<div class='gauge-label'>Solar Radiation</div>", unsafe_allow_html=True)

    with g3:
        st.plotly_chart(
            gauge_chart(latest_live["Cloud_Cover"], CLOUD_COVER_MAX, "%"),
            use_container_width=True,
            config={"displayModeBar": False},
        )
        st.markdown("<div class='gauge-label'>Cloud Cover</div>", unsafe_allow_html=True)

    left_col, right_col = st.columns(2)

    with left_col:
        st.plotly_chart(
            build_power_chart(live_df),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    with right_col:
        if forecast_2d.empty:
            st.warning("No forecast data found.")
        else:
            st.plotly_chart(
                build_weather_forecast_chart(forecast_2d),
                use_container_width=True,
                config={"displayModeBar": False},
            )

    st.markdown(
        f"""
        <div class="next3h-card {rating_class}">
            <div class="next3h-title">NEXT 3 HOURS</div>
            <div class="next3h-value">{rating_icon} {rating_text}</div>
            <div class="next3h-sub">{rating_sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
