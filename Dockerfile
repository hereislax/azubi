FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    gcc \
    locales \
    curl \
    gnupg \
    ca-certificates \
    && echo "deb http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client-17 \
        restic \
        openssh-client \
    && echo "de_DE.UTF-8 UTF-8" > /etc/locale.gen \
    && locale-gen \
    && update-locale LANG=de_DE.UTF-8 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --no-create-home --shell /bin/false appuser

ENV LANG=de_DE.UTF-8 \
    LANGUAGE=de_DE:de \
    LC_ALL=de_DE.UTF-8

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN SECRET_KEY=dummy-build-key python manage.py collectstatic --noinput \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["gunicorn", "Azubi.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
