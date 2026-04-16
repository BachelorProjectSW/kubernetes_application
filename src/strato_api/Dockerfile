FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/strato_api ./strato_api
COPY src/db ./db
COPY src/models ./models
COPY src/custom_logging ./custom_logging

EXPOSE 8090

CMD ["uvicorn", "strato_api.app:app", "--host", "0.0.0.0", "--port", "8090"]