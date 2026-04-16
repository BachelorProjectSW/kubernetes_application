FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates

COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

ENV PYTHONPATH=/app
COPY src /app/src

CMD ["uvicorn", "src.global_api.app:app", "--host", "0.0.0.0", "--port", "8020"]
