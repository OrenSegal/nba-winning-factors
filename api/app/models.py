from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ProcessingRequest(BaseModel):
    seasons: List[str] = Field(
        ...,  # ... means required
        description="List of NBA seasons to process (e.g., ['2021-22', '2022-23'])",
        example=["2022-23"]
    )

class ProcessingResponse(BaseModel):
    message: str = Field(
        ...,
        description="Status message about the processing request"
    )
    job_id: str = Field(
        ...,
        description="Unique identifier for tracking the processing job"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp of when the processing request was received"
    )

class ProcessingError(BaseModel):
    error: str = Field(
        ...,
        description="Error message describing what went wrong"
    )
    job_id: Optional[str] = Field(
        None,
        description="Job ID if the error occurred during processing"
    )

class ProcessingStatus(BaseModel):
    job_id: str
    status: str = Field(
        ...,
        description="Current status of the processing job"
    )
    progress: float = Field(
        ...,
        description="Processing progress (0-100)",
        ge=0,
        le=100
    )
    metrics: Optional[dict] = Field(
        None,
        description="Current metrics from the processing job"
    )