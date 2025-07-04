# Dockerfile

FROM python:3.11-slim-buster 

ENV PYTHONDONTWRITEBYTECODE = 1
ENV PYTHONUNBUFFERED = 1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        pkg-config \
        libmariadb-dev-compat \ 
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code
COPY . .

# Set the working directory for Django commands to where 'manage.py' is.
# This simplifies running Django management commands.
WORKDIR /app/surgicalm

# Reset the working directory to /app for consistent Gunicorn execution.
WORKDIR /app

# Expose the port Gunicorn will listen on inside the container.
EXPOSE 8000

# The command to run the Gunicorn server when the container starts.
# 'gunicorn' runs directly because dependencies were installed globally in the container.
# 'surgicalm.backend.wsgi:application' is the correct Python dotted path from /app.
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:8000", "surgicalm.backend.wsgi:application"]