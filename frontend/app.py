import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import mlflow
from datetime import datetime

# Configure API endpoint
API_URL = "http://api:8000"
MLFLOW_URL = "http://mlflow:5000"

def main():
    st.title("NBA Analytics Dashboard")
    
    # Sidebar for data processing
    st.sidebar.header("Data Processing")
    seasons = st.sidebar.multiselect(
        "Select Seasons",
        options=["2018-19", "2019-20", "2020-21", "2021-22", "2022-23"],
        default=["2022-23"]
    )
    
    if st.sidebar.button("Process Data"):
        with st.spinner("Processing data..."):
            try:
                response = requests.post(
                    f"{API_URL}/process-data",
                    json={"seasons": seasons}
                )
                response.raise_for_status()
                st.success("Data processing started! Check MLflow for progress.")
            except requests.exceptions.RequestException as e:
                st.error(f"Error: {str(e)}")
    
    # MLflow runs visualization
    st.header("MLflow Experiments")
    try:
        mlflow.set_tracking_uri(MLFLOW_URL)
        runs = mlflow.search_runs(experiment_names=["nba-analytics"])
        if not runs.empty:
            runs_df = runs[["start_time", "metrics.total_games", "metrics.avg_pace", "metrics.avg_points"]]
            runs_df["start_time"] = pd.to_datetime(runs_df["start_time"]).dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(runs_df)
            
            # Metrics visualization
            st.subheader("Metrics Trends")
            fig = px.line(runs_df, x="start_time", y="metrics.avg_points", title="Average Points per Game")
            st.plotly_chart(fig)
    except Exception as e:
        st.error(f"Error connecting to MLflow: {str(e)}")
    
    # Data viewer
    st.header("Processed Data Viewer")
    try:
        latest_run = mlflow.search_runs(experiment_names=["nba-analytics"]).iloc[0]
        artifacts_path = latest_run.artifact_uri
        if artifacts_path:
            data_path = artifacts_path.replace("mlflow-artifacts:", "/mlflow/artifacts")
            df = pd.read_csv(f"{data_path}/processed_data_{hash(tuple(seasons))}.csv")
            st.dataframe(df)
            
            # Data visualizations
            st.subheader("Data Visualizations")
            metric_col = st.selectbox("Select Metric", df.select_dtypes(include=['float64', 'int64']).columns)
            fig = px.histogram(df, x=metric_col, title=f"Distribution of {metric_col}")
            st.plotly_chart(fig)
    except Exception as e:
        st.warning("No processed data available yet.")

if __name__ == "__main__":
    main()