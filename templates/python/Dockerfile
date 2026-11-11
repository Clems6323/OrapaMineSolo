# Image de la soumission : le point d'entrée parle le protocole sur stdin/stdout.
# Aucune dépendance hors stdlib — le client (orapa_client.py) est embarqué.
FROM python:3.12-slim

WORKDIR /app
COPY orapa_client.py main.py ./

# Le solveur lit l'arbitre sur stdin et écrit ses commandes sur stdout.
ENTRYPOINT ["python", "main.py"]
