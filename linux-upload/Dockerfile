FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .
COPY static/ static/

RUN mkdir -p uploads

ENV UVICORN_PORT=8787

EXPOSE 8787

CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8787"]
