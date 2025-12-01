# Infrastructure as Code with Pulumi

This directory contains Pulumi infrastructure code that manages all Google Cloud Platform resources for the karaoke generator backend.

## What This Replaces

This replaces the manual setup in:
- `backend/setup-gcp.sh` (shell script)
- `docs/GCP-SETUP.md` (manual instructions)

## Resources Managed

This Pulumi program manages:
- **Firestore Database**: Native mode database for job state
- **Cloud Storage Bucket**: For uploads, outputs, and temp files
- **Artifact Registry**: Docker repository for backend images
- **Service Account**: For Cloud Run with appropriate IAM roles
- **Secrets**: Secret Manager secrets (you add the values)
- **IAM Bindings**: All necessary permissions

## Prerequisites

1. **Pulumi CLI**: Install with `brew install pulumi`
2. **Pulumi Account**: Sign up at https://app.pulumi.com
3. **Google Cloud SDK**: Already installed
4. **Python 3.10+**: For running Pulumi Python

## Setup

```bash
cd infrastructure

# Login to Pulumi (interactive)
pulumi login

# Create a new stack (e.g., "dev" or "prod")
pulumi stack init dev

# Set your GCP project
pulumi config set gcp:project nomadkaraoke
pulumi config set gcp:region us-central1

# Install Python dependencies
pip install -r requirements.txt
```

## Usage

### Preview Changes

```bash
pulumi preview
```

This shows you what will be created/updated/deleted without making changes.

### Apply Changes

```bash
pulumi up
```

This prompts you to confirm, then applies the changes.

### View Current State

```bash
pulumi stack output
```

Shows all exported values (bucket name, service account email, etc.)

### Destroy Everything

```bash
pulumi destroy
```

**Warning**: This deletes all infrastructure!

## Adding Secret Values

After running `pulumi up`, you need to add the actual secret values:

```bash
# Add AudioShake API key
echo -n "your-audioshake-key" | \
  gcloud secrets versions add audioshake-api-key --data-file=-

# Add Genius API key  
echo -n "your-genius-key" | \
  gcloud secrets versions add genius-api-key --data-file=-

# Add Audio Separator API URL
echo -n "https://your-modal-url" | \
  gcloud secrets versions add audio-separator-api-url --data-file=-
```

Or use Pulumi config secrets:

```bash
pulumi config set --secret audioshake-api-key "your-key"
pulumi config set --secret genius-api-key "your-key"
pulumi config set audio-separator-api-url "https://your-modal-url"
```

Then update `__main__.py` to create secret versions with these values.

## Deploying Cloud Run

After infrastructure is set up, deploy Cloud Run separately:

```bash
# Build image
gcloud builds submit --config=../cloudbuild.yaml --timeout=20m

# Deploy (using outputs from Pulumi)
SA_EMAIL=$(pulumi stack output service_account_email)
BUCKET_NAME=$(pulumi stack output bucket_name)

gcloud run deploy karaoke-backend \
  --image us-central1-docker.pkg.dev/nomadkaraoke/karaoke-repo/karaoke-backend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account $SA_EMAIL \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --max-instances 10 \
  --min-instances 1 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=nomadkaraoke,GCS_BUCKET_NAME=$BUCKET_NAME,FIRESTORE_COLLECTION=jobs,ENVIRONMENT=production,LOG_LEVEL=INFO" \
  --set-secrets="AUDIOSHAKE_API_KEY=audioshake-api-key:latest,GENIUS_API_KEY=genius-api-key:latest,AUDIO_SEPARATOR_API_URL=audio-separator-api-url:latest"
```

## Benefits

✅ **Reproducible**: Run `pulumi up` to create identical infrastructure
✅ **Tracked**: All resources are tracked in Pulumi state
✅ **Versioned**: Infrastructure changes are in git
✅ **Safe**: Preview changes before applying
✅ **Documented**: Code is self-documenting
✅ **Collaborative**: Team can see and modify infrastructure

## State Management

Pulumi state is stored in Pulumi Cloud by default. This includes:
- Current infrastructure state
- Resource IDs and properties
- Stack outputs
- Configuration values

## Multi-Environment

To create separate environments:

```bash
# Create dev stack
pulumi stack init dev
pulumi config set gcp:project nomadkaraoke-dev
pulumi up

# Create prod stack
pulumi stack init prod
pulumi config set gcp:project nomadkaraoke
pulumi up

# Switch between stacks
pulumi stack select dev
pulumi stack select prod
```

## Troubleshooting

### "Resource already exists"

If resources were created manually, you can import them:

```bash
pulumi import gcp:storage/bucket:Bucket karaoke-storage karaoke-gen-storage-nomadkaraoke
```

### Permissions errors

Ensure your gcloud account has:
- Owner or Editor role on the project
- Or specific roles: Cloud Build Editor, Storage Admin, etc.

### State conflicts

If multiple people are working:
```bash
pulumi refresh  # Sync state with actual cloud resources
```

## Next Steps

1. Run `pulumi up` to create infrastructure
2. Add secret values
3. Build and deploy Cloud Run service
4. Update documentation to reference Pulumi workflow

