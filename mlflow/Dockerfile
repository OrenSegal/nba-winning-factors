FROM python:3.9-slim

WORKDIR /mlflow

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set environment variable for protobuf
ENV PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directories for MLflow
RUN mkdir -p /mlflow/mlruns /mlflow/artifacts

# Expose port
EXPOSE 5000

# Start MLflow server
CMD ["mlflow", "server", \
     "--host", "0.0.0.0", \
     "--port", "5000", \
     "--backend-store-uri", "sqlite:///mlflow.db", \
     "--default-artifact-root", "/mlflow/artifacts"]