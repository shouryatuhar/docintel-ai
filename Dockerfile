FROM python:3.11-slim

WORKDIR /app

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY samples/ ./samples/

ENTRYPOINT ["python", "src/main.py"]
CMD ["--help"]
