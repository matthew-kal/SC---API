# Dockerfile

# --- Build Stage ---
# This stage just gets our OS dependencies and Python packages ready
FROM python:3.11-slim-bullseye as builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libmariadb-dev-compat \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


# --- Final Stage ---
# This is the final, lean image we will actually use
FROM python:3.11-slim-bullseye as final

WORKDIR /app

# Install only the OS packages needed to RUN the app
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libmariadb-dev-compat \
    && rm -rf /var/lib/apt/lists/*

# Create the non-root user
RUN addgroup --system app && adduser --system --group app

# Copy the pre-compiled Python packages from the builder stage,
# and give ownership to the 'app' user.
COPY --from=builder --chown=app:app /app/wheels /wheels

# Copy the application code and give ownership to the 'app' user
COPY --chown=app:app . .

# Switch to the non-root user
USER app

# Set the PATH to include the user's local bin directory
ENV PATH="/home/app/.local/bin:${PATH}"

# Now, as the 'app' user, install the packages to the local bin directory
RUN pip install --no-cache-dir --user /wheels/*

# Set the final working directory
WORKDIR /app/surgicalm

ENV PYTHONPATH /app


EXPOSE 8000

CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "surgicalm.backend.wsgi:application"]