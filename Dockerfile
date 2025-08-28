# Dockerfile

FROM python:3.11-slim-bullseye as builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libmariadb-dev-compat \
        default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt

FROM python:3.11-slim-bullseye as final

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmariadb-dev-compat \
        default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system app && adduser --system --group app

COPY --from=builder --chown=app:app /app/wheels /wheels

COPY --chown=app:app . .

USER app

ENV PATH="/home/app/.local/bin:${PATH}"

RUN pip install --no-cache-dir --user /wheels/*

WORKDIR /app/surgicalm

ENV PYTHONPATH /app

EXPOSE 8080

CMD ["sh", "-c", "gunicorn --workers 2 --bind 0.0.0.0:${PORT:-8080} surgicalm.backend.wsgi:application"]