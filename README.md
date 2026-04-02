# Solar Energy Monitoring Dashboard

A portfolio-ready end-to-end solar monitoring project that combines live operational data with weather forecast data for real-time visibility, short-term planning, and historical analysis.

## Project overview

This project was built to monitor solar power generation and enrich it with weather context such as solar radiation, cloud cover, wind speed, and forecast information. The system brings together data ingestion, transformation, database storage, and dashboard visualization in one workflow.

## What the project does

- collects live solar and weather-related data on a recurring schedule
- stores live and historical data in MySQL
- collects weather forecast data for the next 2–3 days
- supports dashboard views for live operations and management analysis
- visualizes KPIs, trends, forecast windows, and day-level planning signals

## Dashboards

### 1. Production dashboard
Focuses on operational monitoring:
- current power
- current solar radiation
- current cloud cover
- live power utilization trend
- short-term weather forecast
- next 3 hours solar suitability rating

### 2. Management dashboard
Focuses on analysis and planning:
- historical KPIs
- aggregated raw / hourly / daily views
- trend charts
- solar vs power / cloud vs power relationship analysis
- forecast-based day quality assessment
- daily summary table
- day-to-day comparison

## Architecture

1. data is fetched from external solar and weather APIs
2. data is cleaned and transformed in Python
3. processed records are sent to a MySQL database
4. Streamlit dashboards read from MySQL and visualize live + forecast + historical views

## Tech stack

- Python
- Pandas
- MySQL / MariaDB
- Streamlit
- Plotly
- PHP endpoints for database insert/upsert
- Jupyter / notebook-based prototyping

## Public repository notes

This public version is anonymized:
- no credentials are included
- company-specific branding was removed
- secrets are expected via Streamlit `secrets.toml` or environment variables
- screenshots are mock previews generated from the dashboard structure

## Suggested repository structure

```text
solar-energy-monitoring-dashboard/
├── dashboard/
│   ├── production_dashboard.py
│   └── management_dashboard.py
├── docs/
│   ├── production_dashboard_mock.png
│   └── management_dashboard_mock.png
├── README.md
├── requirements.txt
├── .gitignore
└── .streamlit/
    └── secrets.toml.example
```

## How to run

1. create a virtual environment
2. install dependencies from `requirements.txt`
3. copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
4. fill in your database values
5. run one of the dashboards:

```bash
streamlit run dashboard/production_dashboard.py
```

or

```bash
streamlit run dashboard/management_dashboard.py
```

## Future improvements

- modular ETL package outside notebooks
- centralized logging
- input validation layer
- tests for transformation logic
- anomaly detection and alerting
- forecast accuracy monitoring
