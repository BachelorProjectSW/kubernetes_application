FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt


COPY src/global_api /app/src/global_api
COPY src/cluster_api /app/src/cluster_api
COPY src/custom_logging /app/src/custom_logging
COPY src/models /app/src/models
COPY src/db /app/src/db

CMD ["uvicorn", "src.global_api.app:app", "--host", "0.0.0.0", "--port", "8020"]
