FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY frontend/ ./frontend/
COPY samples/ ./samples/

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
