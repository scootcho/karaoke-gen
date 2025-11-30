#!/bin/bash

# Google Cloud Platform Setup Script
# This script sets up all required GCP infrastructure for the karaoke generator backend

set -e

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo "Error: PROJECT_ID environment variable is not set"
    echo "Usage: export PROJECT_ID=your-project-id && ./setup-gcp.sh"
    exit 1
fi

echo "Setting up GCP infrastructure for project: $PROJECT_ID"

# Set project
gcloud config set project $PROJECT_ID

# Enable APIs
echo "Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com

# Create Firestore database
echo "Creating Firestore database..."
if ! gcloud firestore databases describe --format="value(name)" 2>/dev/null; then
    gcloud firestore databases create \
      --region=us-central \
      --type=firestore-native
    echo "Firestore database created"
else
    echo "Firestore database already exists"
fi

# Create Cloud Storage bucket
echo "Creating Cloud Storage bucket..."
BUCKET_NAME="karaoke-gen-storage-$PROJECT_ID"
if ! gsutil ls gs://$BUCKET_NAME 2>/dev/null; then
    gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://$BUCKET_NAME
    echo "Bucket created: gs://$BUCKET_NAME"
else
    echo "Bucket already exists: gs://$BUCKET_NAME"
fi

# Set lifecycle policy
echo "Setting lifecycle policy..."
cat > /tmp/lifecycle.json <<EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {
          "age": 7,
          "matchesPrefix": ["temp/", "uploads/"]
        }
      }
    ]
  }
}
EOF
gsutil lifecycle set /tmp/lifecycle.json gs://$BUCKET_NAME

# Create service account
echo "Creating service account..."
SA_NAME="karaoke-backend"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe $SA_EMAIL 2>/dev/null; then
    gcloud iam service-accounts create $SA_NAME \
      --display-name="Karaoke Backend Service Account"
    echo "Service account created: $SA_EMAIL"
else
    echo "Service account already exists: $SA_EMAIL"
fi

# Grant permissions
echo "Granting permissions to service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/datastore.user" \
  --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.objectAdmin" \
  --condition=None

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor" \
  --condition=None

echo ""
echo "✅ GCP infrastructure setup complete!"
echo ""
echo "Next steps:"
echo "1. Create secrets in Secret Manager:"
echo "   - audioshake-api-key"
echo "   - genius-api-key"
echo "   - audio-separator-api-url"
echo ""
echo "2. Build and deploy the backend:"
echo "   cd /Users/andrew/Projects/karaoke-gen"
echo "   gcloud builds submit --tag gcr.io/$PROJECT_ID/karaoke-backend -f backend/Dockerfile ."
echo ""
echo "3. Deploy to Cloud Run:"
echo "   gcloud run deploy karaoke-backend \\"
echo "     --image gcr.io/$PROJECT_ID/karaoke-backend \\"
echo "     --region us-central1 \\"
echo "     --service-account $SA_EMAIL \\"
echo "     --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCS_BUCKET_NAME=$BUCKET_NAME"
echo ""
echo "Bucket name: $BUCKET_NAME"
echo "Service account: $SA_EMAIL"

