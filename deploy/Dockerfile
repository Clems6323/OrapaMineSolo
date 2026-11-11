# Image du serveur officiel (UI Streamlit + worker partagent cette image).
# Build depuis la racine du dépôt :  docker build -f deploy/Dockerfile -t orapa-server .
FROM python:3.12-slim

WORKDIR /app

# Dépendances : le paquet + Streamlit (hors cœur). Le worker a besoin du client
# `docker` et de `git` pour cloner/construire les soumissions.
RUN apt-get update && apt-get install -y --no-install-recommends git docker.io \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir . streamlit

ENV ORAPA_DB=/data/orapa.sqlite3 \
    ORAPA_GRIDS=/data/official_grids

# UI par défaut ; le worker surcharge la commande (voir docker-compose).
EXPOSE 8501
CMD ["streamlit", "run", "src/orapa_mine/server/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
