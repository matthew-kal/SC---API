#!/bin/bash

echo "--- Starting Production Environment (Verbose Logging) ---"

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker."
  exit 1
fi

# Ensure .env exists in the root (SC---API/) directory
if [ ! -f .env ]; then
  echo "Error: .env file not found. Please create it in the SC---API/ directory."
  echo "WARNING: This file contains sensitive production credentials and should NEVER be committed to Git!"
  exit 1
fi

echo ""
echo "--- Building Docker images for production (Verbose Output) ---"
# Correct syntax: --verbose comes after docker-compose, before -f flags and subcommand
docker compose --verbose -f docker-compose.yml -f docker-builds/docker-compose.prod.yaml build

if [ $? -ne 0 ]; then
  echo "Error: Docker image build failed for production. Check the verbose output above. Exiting."
  exit 1
fi

echo ""
echo "--- Starting production services (Web and Nginx containers) ---"
# Correct syntax: --verbose after docker-compose, -f flags, then up -d
docker compose --verbose -f docker-compose.yml -f docker-builds/docker-compose.prod.yaml up -d

if [ $? -ne 0 ]; then
  echo "Error: Failed to start production services. Check the verbose output above. Exiting."
  exit 1
fi

# REMOVED: Running database migrations section

# REMOVED: Collecting static files section

echo ""
echo "--- Production services are now running! ---"
echo "--- Streaming Container Logs ---"
echo "This will show live activity inside your running containers."
echo "Press Ctrl+C to stop streaming logs and return to the script's end."
echo ""
# Correct syntax: --verbose after docker-compose, -f flags, then logs -f
docker compose --verbose -f docker-compose.yml -f docker-builds/docker-compose.prod.yaml logs -f

echo ""
echo "--- Script finished. To stop services: docker-compose -f docker-compose.yml -f docker-builds/docker-compose.prod.yaml down ---"
echo "Remember to configure your AWS EC2 Security Group (ports 80/443 inbound) and RDS Security Group."
echo "Access your app at: https://api.surgicalm.com"