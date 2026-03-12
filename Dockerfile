FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

EXPOSE 8040

ENV KUBECONFIG=/app/src/cluster_api/auth/k3d-devcluster.yaml

WORKDIR /app/src

CMD ["python", "-m", "cluster_api.kube_api_server"]
