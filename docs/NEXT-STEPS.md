# Next Steps: Deploy Backend to Cloud Run

## ✅ Completed
1. ✅ Infrastructure as Code with Pulumi
2. ✅ Docker build with caching
3. ✅ Permissions fixed and tested
4. ✅ Backend image built successfully
5. ✅ Cleanup: Test images removed, deprecated scripts marked

## 🎯 Next: Deploy to Cloud Run

### Step 1: Deploy the Backend Service

```bash
# Get Pulumi outputs for configuration
cd infrastructure
BUCKET_NAME=$(pulumi stack output bucket_name)
SA_EMAIL=$(pulumi stack output service_account_email)
PROJECT_ID=$(pulumi stack output project_id)
ARTIFACT_REPO=$(pulumi stack output artifact_repo_url)

# Deploy to Cloud Run
gcloud run deploy karaoke-backend \
  --image ${ARTIFACT_REPO}/karaoke-backend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --service-account ${SA_EMAIL} \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --max-instances 10 \
  --min-instances 0 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GCS_BUCKET_NAME=${BUCKET_NAME},FIRESTORE_COLLECTION=jobs,ENVIRONMENT=production,LOG_LEVEL=INFO" \
  --set-secrets="AUDIOSHAKE_API_KEY=audioshake-api-key:latest,GENIUS_API_KEY=genius-api-key:latest,AUDIO_SEPARATOR_API_URL=audio-separator-api-url:latest"
```

### Step 2: Test the Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe karaoke-backend \
  --region us-central1 \
  --format='value(status.url)')

echo "Service URL: $SERVICE_URL"

# Test health endpoint
curl $SERVICE_URL/api/health

# Expected response:
# {"status":"healthy","service":"karaoke-gen-backend"}
```

### Step 3: Verify Secrets Access

If secrets aren't properly configured, add versions:

```bash
# Add AudioShake API key
echo -n "YOUR_AUDIOSHAKE_KEY" | \
  gcloud secrets versions add audioshake-api-key --data-file=-

# Add Genius API key  
echo -n "YOUR_GENIUS_KEY" | \
  gcloud secrets versions add genius-api-key --data-file=-

# Add Audio Separator API URL
echo -n "YOUR_AUDIO_SEPARATOR_URL" | \
  gcloud secrets versions add audio-separator-api-url --data-file=-
```

## 🚀 Future Steps (Phase 2)

After backend is deployed and tested:

### 1. Create React Frontend
- Set up Vite + React + TypeScript project
- Implement job submission UI
- Add status polling and progress display
- Style with Tailwind CSS

### 2. Deploy to Cloudflare Pages
- Connect GitHub repository
- Configure build settings
- Set environment variable for backend API URL

### 3. End-to-End Testing
- Test full workflow: upload → process → download
- Test with YouTube URLs
- Test concurrent jobs
- Test error handling

### 4. Performance Optimization
- Configure Cloud Run autoscaling
- Set up Cloud CDN (if needed)
- Optimize frontend bundle size

### 5. Monitoring & Observability
- Set up Cloud Logging dashboards
- Configure error alerting
- Track job completion rates

## 📊 Current Architecture

```
┌─────────────────────────┐
│   Cloudflare Pages      │  (React Frontend - Phase 2)
│   gen.nomadkaraoke.com  │
└────────────┬────────────┘
             │ HTTPS
             ▼
┌─────────────────────────┐
│   Cloud Run Service     │  ← YOU ARE HERE
│   karaoke-backend       │
│   (FastAPI)             │
└────────┬────────────────┘
         │
         ├──► Firestore (job state)
         ├──► Cloud Storage (files)
         ├──► Secret Manager (API keys)
         └──► Audio Separator API (GPU)
```

## 🔧 Troubleshooting

### Issue: Cloud Run deployment fails

Check service account permissions:
```bash
gcloud projects get-iam-policy nomadkaraoke \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:karaoke-backend@*"
```

### Issue: Secrets not found

Verify secrets exist and have values:
```bash
gcloud secrets list
gcloud secrets versions list audioshake-api-key
```

### Issue: Container fails to start

Check logs:
```bash
gcloud logging read "resource.type=cloud_run_revision \
  AND resource.labels.service_name=karaoke-backend \
  AND severity>=ERROR" --limit 50
```

## 📝 Notes

- Cloud Run cold start time: ~3-5 seconds
- Timeout set to 600s for long video processing
- Min instances: 0 (cost optimization)
- Max instances: 10 (prevents runaway costs)
- Memory: 2Gi (sufficient for video processing)
- CPU: 2 (good balance for performance)

## 🎯 Success Criteria

Before moving to Phase 2, verify:
- [ ] Health endpoint returns 200 OK
- [ ] Can submit a job via API
- [ ] Job progresses through states (queued → processing → completed)
- [ ] Output files stored in Cloud Storage
- [ ] No permission errors in logs

---

**Current Status**: Ready to deploy to Cloud Run!

Run the commands in Step 1 to deploy the backend service.

