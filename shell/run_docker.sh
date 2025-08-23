#!/bin/bash

echo "--- Starting Local Development Environment ---"

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker Desktop or Docker Engine."
  exit 1
fi

# Ensure .env exists in the root (SC---API/) directory
if [ ! -f .env ]; then
  echo "Error: .env file not found. Please create it in the SC---API/ directory."
  echo "WARNING: This file contains sensitive credentials and should NEVER be committed to Git!"
  exit 1
fi

echo "--- Building Docker images for local setup (Verbose Output) ---"
docker-compose --verbose -f docker-compose.yml build

if [ $? -ne 0 ]; then
  echo "Error: Docker image build failed for local setup. Exiting."
  exit 1
fi

echo ""
echo "--- Starting local services (Web and Nginx containers) ---" # <-- UPDATED MESSAGE
docker-compose --verbose -f docker-compose.yml up -d

if [ $? -ne 0 ]; then
  echo "Error: Failed to start local services. Exiting."
  exit 1
fi

# Removed: Running database migrations for local setup
# Removed: Collecting static files for local setup

echo ""
echo "--- Local services are now running! ---" # <-- UPDATED MESSAGE
echo "You can check logs with: docker-compose -f docker-compose.yml logs -f"
echo "Access your app at: http://localhost:8000" 
echo "To stop services: docker-compose -f docker-compose.yml down"