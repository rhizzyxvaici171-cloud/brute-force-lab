# Brute Force Lab — intentionally vulnerable teaching app.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# 2 workers / 4 threads is plenty for a classroom. Students' brute-force
# traffic hits a single process fine.
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4"]
