# Google Cloud Platform Setup Guide

This guide walks through setting up the Google Cloud infrastructure for the karaoke generation backend.

## Prerequisites

- Google Cloud Project with billing enabled
- `gcloud` CLI installed and configured
- Appropriate IAM permissions

## Step 1: Enable Required APIs

```bash
# Set your project ID
export PROJECT_ID=your-project-id
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  firestore.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com
```

## Step 2: Create Firestore Database

```bash
# Create Firestore database in native mode
gcloud firestore databases create \
  --region=us-central \
  --type=firestore-native

# Create indexes (if needed)
# Firestore will auto-create simple indexes, but composite indexes need to be defined
```

## Step 3: Create Cloud Storage Bucket

```bash
# Create bucket for file storage
gsutil mb -p $PROJECT_ID -c STANDARD -l us-central1 gs://karaoke-gen-storage

# Set lifecycle policy to delete temp files after 7 days
cat > lifecycle.json <<EOF
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

gsutil lifecycle set lifecycle.json gs://karaoke-gen-storage

# Set CORS policy for direct uploads (if needed)
cat > cors.json <<EOF
[
  {
    "origin": ["https://gen.nomadkaraoke.com"],
    "method": ["GET", "POST", "PUT"],
    "responseHeader": ["Content-Type"],
    "maxAgeSeconds": 3600
  }
]
EOF

gsutil cors set cors.json gs://karaoke-gen-storage
```

## Step 4: Create Secrets

Store sensitive API keys in Secret Manager:

```bash
# AudioShake API Key
echo -n "your-audioshake-key" | \
  gcloud secrets create audioshake-api-key \
    --data-file=- \
    --replication-policy="automatic"

# Genius API Key
echo -n "your-genius-key" | \
  gcloud secrets create genius-api-key \
    --data-file=- \
    --replication-policy="automatic"

# Audio Separator API URL
echo -n "https://your-modal-deployment.modal.run" | \
  gcloud secrets create audio-separator-api-url \
    --data-file=- \
    --replication-policy="automatic"
```

## Step 5: Create Service Account

Create a service account for Cloud Run with appropriate permissions:

```bash
# Create service account
gcloud iam service-accounts create karaoke-backend \
  --display-name="Karaoke Backend Service Account"

# Grant permissions
SA_EMAIL=karaoke-backend@$PROJECT_ID.iam.gserviceaccount.com

# Firestore access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/datastore.user"

# Cloud Storage access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.objectAdmin"

# Secret Manager access
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

## Step 6: Build and Deploy Backend

```bash
# Navigate to project root
cd /Users/andrew/Projects/karaoke-gen

# Build container image
gcloud builds submit \
  --tag gcr.io/$PROJECT_ID/karaoke-backend \
  --timeout=20m \
  -f backend/Dockerfile .

# Deploy to Cloud Run
gcloud run deploy karaoke-backend \
  --image gcr.io/$PROJECT_ID/karaoke-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account $SA_EMAIL \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GCS_BUCKET_NAME=karaoke-gen-storage,FIRESTORE_COLLECTION=jobs,ENVIRONMENT=production,LOG_LEVEL=INFO" \
  --set-secrets="AUDIOSHAKE_API_KEY=audioshake-api-key:latest,GENIUS_API_KEY=genius-api-key:latest,AUDIO_SEPARATOR_API_URL=audio-separator-api-url:latest"
```

## Step 7: Configure Domain (Optional)

```bash
# Map custom domain to Cloud Run service
gcloud run domain-mappings create \
  --service karaoke-backend \
  --domain api.nomadkaraoke.com \
  --region us-central1

# Follow the instructions to update DNS records
```

## Step 8: Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe karaoke-backend \
  --region us-central1 \
  --format='value(status.url)')

# Test health endpoint
curl $SERVICE_URL/api/health

# Should return: {"status":"healthy","service":"karaoke-gen-backend"}
```

## Environment Variables Reference

The following environment variables are configured in Cloud Run:

- `GOOGLE_CLOUD_PROJECT`: Your GCP project ID
- `GCS_BUCKET_NAME`: Cloud Storage bucket name
- `FIRESTORE_COLLECTION`: Firestore collection for jobs (default: "jobs")
- `ENVIRONMENT`: deployment environment (production/staging/development)
- `LOG_LEVEL`: logging level (INFO/DEBUG/WARNING/ERROR)
- `MAX_CONCURRENT_JOBS`: maximum concurrent processing jobs
- `JOB_TIMEOUT_SECONDS`: timeout for job processing

Secrets (from Secret Manager):
- `AUDIOSHAKE_API_KEY`: AudioShake transcription API key
- `GENIUS_API_KEY`: Genius lyrics API key
- `AUDIO_SEPARATOR_API_URL`: URL for audio separator GPU API

## Monitoring and Logging

View logs in Cloud Logging:

```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend" \
  --limit 50 \
  --format json

# Stream logs
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend"
```

## Cost Estimation

Approximate costs for moderate usage (100 jobs/month):

- Cloud Run: ~$10-30/month (based on execution time)
- Cloud Storage: ~$1-5/month (20GB storage)
- Firestore: ~$1-5/month (small read/write volume)
- Total: ~$15-40/month

Note: Audio separator GPU processing (if using Modal) is separate.

## Troubleshooting

### Issue: Container fails to start

Check logs:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=karaoke-backend AND severity>=ERROR" --limit 20
```

### Issue: Permission denied errors

Verify service account permissions:
```bash
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:karaoke-backend@$PROJECT_ID.iam.gserviceaccount.com"
```

### Issue: Secrets not found

List and verify secrets:
```bash
gcloud secrets list
gcloud secrets versions access latest --secret=audioshake-api-key
```

## Updating the Service

To deploy updates:

```bash
# Rebuild image
gcloud builds submit --tag gcr.io/$PROJECT_ID/karaoke-backend -f backend/Dockerfile .

# Deploy will automatically use new image
gcloud run deploy karaoke-backend \
  --image gcr.io/$PROJECT_ID/karaoke-backend \
  --region us-central1
```

## Cleanup (if needed)

To delete all resources:

```bash
# Delete Cloud Run service
gcloud run services delete karaoke-backend --region us-central1

# Delete storage bucket
gsutil -m rm -r gs://karaoke-gen-storage

# Delete secrets
gcloud secrets delete audioshake-api-key
gcloud secrets delete genius-api-key
gcloud secrets delete audio-separator-api-url

# Delete service account
gcloud iam service-accounts delete karaoke-backend@$PROJECT_ID.iam.gserviceaccount.com
```

