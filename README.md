# Solar Energy Monitoring Dashboard

Dashboard and data pipeline for monitoring solar energy generation and supporting production planning based on energy availability.

---

## 📊 Dashboard Preview

![Production Dashboard](images/Solar_Dashboard.png)

---

## 🎯 Business Context

In industrial environments, energy availability directly impacts how and when production can run.

This project demonstrates how solar generation data and weather forecasts can be combined to:
- monitor real-time energy production  
- anticipate short-term availability  
- support data-driven production planning  

---

## ⚙️ What this system does

- Collects live solar and weather data  
- Integrates short-term weather forecasts (2–3 days)  
- Stores time-series data in MySQL  
- Provides dashboards for both operations and management  
- Translates raw data into actionable planning signals  

---

## 🧭 Dashboard Views

### 🔋 Production Dashboard (Operational)
Focus: **real-time monitoring and short-term decisions**

- current power & solar radiation  
- short-term forecast (next hours)  
- power trend (last hours)  
- solar suitability indicator  

---

### 📈 Management Dashboard (Analytical)
Focus: **trend analysis and planning**

- historical KPIs  
- daily / hourly aggregation  
- solar vs power relationships  
- forecast-based day quality  
- production planning insights  

---

## 🏗️ System Architecture

Solar API + Weather API
↓
Python (ETL)
↓
MySQL Database
↓
Streamlit Dashboards

---

## 🧰 Tech Stack

- Python (pandas, requests)  
- MySQL / MariaDB  
- Streamlit  
- Plotly  
- PHP endpoints for data ingestion  

---

## 🔒 Public Repository Notes

This version is adapted for portfolio use:

- Uses anonymized / demo data  
- No credentials or company systems included  
- Dashboard visuals represent structure, not real production data  

---

## ▶️ How to Run

```bash
pip install -r requirements.txt
streamlit run dashboard/production_dashboard.py
