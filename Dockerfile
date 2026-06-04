FROM python:3.11-slim

RUN pip install --no-cache-dir websockets

WORKDIR /app
COPY server.py .
COPY index.html .

EXPOSE 8765

ENTRYPOINT ["python3", "server.py"]
