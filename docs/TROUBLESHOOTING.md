# Troubleshooting

Operational runbooks for known production issues.

---

## Job stuck at `encoding` status

**Cause:** A Cloud Run deployment killed the poller mid-encoding. The GCE worker finished but nobody received the result. The health service will flag this as `encoding_stuck` after 50 minutes.

**Recovery:**

```bash
# 1. Confirm the job is flagged
curl -s "https://api.nomadkaraoke.com/api/health/job-consistency" \
  -H "X-Admin-Token: $(gcloud secrets versions access latest --secret=admin-tokens --project=nomadkaraoke)" \
  | python3 -m json.tool | grep -A3 "encoding_stuck"

# 2. Check what the GCE worker knows about the job
WORKER_URL=$(gcloud secrets versions access latest --secret=encoding-worker-url --project=nomadkaraoke)
WORKER_KEY=$(gcloud secrets versions access latest --secret=encoding-worker-api-key --project=nomadkaraoke)
curl -s "$WORKER_URL/status/YOUR_JOB_ID" -H "X-API-Key: $WORKER_KEY" | python3 -m json.tool

# 3. Re-trigger the video worker — it will pick up the cached GCE result if encoding
#    already finished, or rejoin the poll if it's still running
curl -X POST "https://api.nomadkaraoke.com/api/internal/workers/video" \
  -H "X-Admin-Token: $(gcloud secrets versions access latest --secret=admin-tokens --project=nomadkaraoke)" \
  -H "Content-Type: application/json" \
  -d '{"job_id": "YOUR_JOB_ID"}'
```

**Note:** SSH-restarting the encoding worker is **not needed** since v0.119.6 (PR #413). The `/encode` endpoint is now idempotent — re-triggering the video worker is sufficient.

---

## GCE encoding worker on wrong wheel version

**Cause:** Worker picks up a new deploy but doesn't restart automatically.

```bash
# Check current wheel version
gcloud compute ssh encoding-worker --zone=us-central1-c --project=nomadkaraoke \
  --command="curl -s http://localhost:8080/health | python3 -m json.tool"

# Restart to pick up latest wheel
gcloud compute ssh encoding-worker --zone=us-central1-c --project=nomadkaraoke \
  --command="sudo systemctl restart encoding-worker"
```
