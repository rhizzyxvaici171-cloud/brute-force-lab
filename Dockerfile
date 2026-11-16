# Brute Force Lab — intentionally vulnerable teaching app.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PORT=5000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

# One worker (with threads) so the 'impossible' level's in-memory lockout
# counter is shared across all requests. Multiple workers would each keep a
# separate copy and the lockout would not trigger. One worker is plenty for a
# classroom.
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8"]
