from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .services.nba_processor import NBADataProcessor
from .models import ProcessingRequest, ProcessingResponse
import mlflow
import mlflow.sklearn
import pandas as pd
from typing import List
import logging

app = FastAPI(title="NBA Analytics API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure MLflow
mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("nba-analytics")

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.post("/process-data", response_model=ProcessingResponse)
async def process_data(request: ProcessingRequest, background_tasks: BackgroundTasks):
    """
    Endpoint to trigger NBA data processing
    """
    try:
        processor = NBADataProcessor(request.seasons)
        
        # Add processing task to background
        background_tasks.add_task(process_and_log_data, processor, request.seasons)
        
        return ProcessingResponse(
            message="Data processing started",
            job_id=str(hash(tuple(request.seasons)))
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def process_and_log_data(processor: NBADataProcessor, seasons: List[str]):
    """
    Process data and log metrics with MLflow
    """
    with mlflow.start_run():
        try:
            # Log parameters
            mlflow.log_param("seasons", seasons)
            
            # Process data
            df = processor.process_data()
            
            # Calculate and log metrics
            metrics = calculate_metrics(df)
            for metric_name, value in metrics.items():
                mlflow.log_metric(metric_name, value)
            
            # Save processed data
            output_path = f"processed_data_{hash(tuple(seasons))}.csv"
            df.to_csv(output_path, index=False)
            mlflow.log_artifact(output_path)
            
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            mlflow.log_param("error", str(e))
            raise

def calculate_metrics(df: pd.DataFrame) -> dict:
    """
    Calculate relevant metrics from the processed data
    """
    return {
        "total_games": len(df["GAME_ID"].unique()),
        "avg_pace": df["PACE"].mean(),
        "avg_points": df["PTS"].mean(),
        # Add more metrics as needed
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {"status": "healthy"}