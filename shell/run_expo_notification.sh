#!/bin/bash

echo "--- Sending Push Notifications ---"

# Default values for title and body
DEFAULT_TITLE="Daily Reminder 🚀"
DEFAULT_BODY="Time to check your app!"

# Parse command-line arguments
TITLE=""
BODY=""

# Loop through arguments to parse --title and --body
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --title)
            TITLE="$2"
            shift # past argument
            ;;
        --body)
            BODY="$2"
            shift # past argument
            ;;
        *)
            echo "Unknown parameter passed: $1"
            echo "Usage: $0 [--title \"Your Title\"] [--body \"Your Body\"]"
            exit 1
            ;;
    esac
    shift # past argument or value
done

# Use default values if not provided
TITLE=${TITLE:-$DEFAULT_TITLE}
BODY=${BODY:-$DEFAULT_BODY}

echo "Notification Title: \"$TITLE\""
echo "Notification Body: \"$BODY\""
echo ""

# Ensure Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Error: Docker is not running. Please start Docker Desktop or Docker Engine."
  exit 1
fi

echo "Running Django management command in web container..."

# Execute the Django management command inside the 'web' container
# Use the production Docker Compose files for this (assuming it's a production task)
# -e PYTHONPATH=/app is added to ensure surgicalm package is found
# Pass the parsed title and body as arguments to the Django command
docker compose -f docker-compose.yml -f docker-builds/docker-compose.local.yml run --rm \
  -e PYTHONPATH=/app \
  web python surgicalm/manage.py send_notifications --title "$TITLE" --body "$BODY"

if [ $? -ne 0 ]; then
  echo "Error: Django management command failed. Check container logs for details."
  exit 1
fi

echo ""
echo "--- Push Notification Command Finished ---"
echo "You can check detailed logs with: docker compose -f docker-compose.yml -f docker-builds/docker-compose.local.yaml logs -f web"