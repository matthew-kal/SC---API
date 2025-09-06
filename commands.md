### Building & Deploying to Google Cloud ###

# Check if Google Cloud Auth is configured for the local machine 

gcloud auth configure-docker us-east4-docker.pkg.dev 

# Builds a container image and pushes it to Artifact Registry.
# This command takes your source code, uses the Dockerfile in your current directory to build a container image, and then pushes that image to Google Artifact Registry. The `--tag` flag specifies the full name and tag for the image. 

export IMAGE_NAME="us-east4-docker.pkg.dev/surgicalm/surgicalm-api-repo/api:latest"
docker build --platform linux/amd64 -t $IMAGE_NAME .
docker push $IMAGE_NAME


# Deploys a container image to Cloud Run.
# This command takes an existing container image from Artifact Registry and deploys it as a new revision to your Cloud Run service. It's how you update your live application.

gcloud run deploy surgicalm-api --image us-east4-docker.pkg.dev/surgicalm/surgicalm-api-repo/api:latest

Choose 36 for region 

---
### Interacting with Your Local Running Container ###

# Executes a command inside a running container.
# This is the primary command you will use to interact with your application without stopping it. It opens a shell inside the specified service container and runs the command you provide.

docker-compose exec web </*insert command */>

# Example: Create new database migrations.
docker-compose exec web python3 manage.py makemigrations

# Example: Apply database migrations.
docker-compose exec web python3 manage.py migrate

# Example: Open a Django shell.
docker-compose exec web python3 manage.py shell