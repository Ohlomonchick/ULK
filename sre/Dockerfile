# Production-oriented web image (Gunicorn + gevent). Migrations and collectstatic run at container start (see compose).
FROM python:3.11-slim-bookworm

LABEL authors="Dmitry"

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# App + sre (gunicorn.conf.py, deployment templates, run_service.sh for host installs, etc.)
COPY . /app

EXPOSE 8002

CMD ["gunicorn", "Cyberpolygon.wsgi:application", "-c", "sre/gunicorn.conf.py"]
