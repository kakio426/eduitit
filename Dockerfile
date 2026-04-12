FROM python:3.12-slim-bookworm

ARG DJANGO_SETTINGS_MODULE=config.settings_production
ARG SECRET_KEY
ARG DATABASE_URL
ARG REDIS_URL
ARG ALLOWED_HOSTS
ARG CLOUDINARY_URL
ARG CLOUDINARY_CLOUD_NAME
ARG CLOUDINARY_API_KEY
ARG CLOUDINARY_API_SECRET

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100 \
    DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE}

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN python manage.py collectstatic --noinput

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py bootstrap_runtime && exec uvicorn config.asgi:application --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --loop uvloop --http httptools --timeout-keep-alive 120"]
