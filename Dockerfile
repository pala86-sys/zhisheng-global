FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8765

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backtest/ backtest/
COPY services/ services/
COPY data/ data/
COPY web/ web/
COPY server.py .

EXPOSE 8765

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8765}"]
