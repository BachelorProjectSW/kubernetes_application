FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt /app/requirements.txt



RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONPATH=/app

COPY src/strato_api /app/src/strato_api
COPY src/global_api /app/src/global_api
COPY src/custom_logging /app/src/custom_logging
COPY src/models /app/src/models
COPY src/db /app/src/db
COPY test /app/test

CMD ["uvicorn", "src.strato_api.app:app", "--host", "0.0.0.0", "--port", "8090"]