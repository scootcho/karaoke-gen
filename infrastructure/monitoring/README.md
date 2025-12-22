# Monitoring Infrastructure

This directory contains Cloud Monitoring dashboard and alerting configurations for the karaoke-gen backend.

## Dashboard

The `dashboard.json` file defines a Cloud Monitoring dashboard with the following panels:

### Overview Metrics
- **Jobs Created (Last Hour)**: Count of jobs created
- **Cloud Run Request Count**: Request rate to the backend
- **Cloud Run Error Rate**: Percentage of non-2xx responses

### Performance Metrics
- **Request Latency (p95)**: 95th percentile response time
- **Cloud Run Instance Count**: Active container instances
- **CPU Utilization**: CPU usage across instances
- **Memory Utilization**: Memory usage across instances

### Cloud Tasks
- **Queue Depth**: Number of tasks waiting in each queue
- **Execution Rate**: Task processing rate per queue

### Logs
- **Worker Logs**: Searchable by `job_id` 
- **Error Logs**: All ERROR-level logs from the backend

## Importing the Dashboard

To import the dashboard into Cloud Monitoring:

```bash
# Using gcloud CLI
gcloud monitoring dashboards create --config-from-file=infrastructure/monitoring/dashboard.json --project=nomadkaraoke
```

Or manually:
1. Go to Cloud Console → Monitoring → Dashboards
2. Click "Create Dashboard"
3. Click "JSON Editor" and paste contents of `dashboard.json`

## Alert Policies

Alert policies are defined in `infrastructure/__main__.py` as Pulumi resources:

### High Error Rate
- **Condition**: >10% of requests return errors for 5+ minutes
- **Severity**: Warning
- **Auto-close**: 1 hour after resolution

### Queue Backlog
- **Condition**: >50 tasks in any queue for 10+ minutes  
- **Severity**: Warning
- **Auto-close**: 30 minutes after resolution

### High Memory Usage
- **Condition**: >85% memory utilization for 5+ minutes
- **Severity**: Warning
- **Auto-close**: 30 minutes after resolution

### Service Unavailable
- **Condition**: No healthy Cloud Run instances for 5+ minutes
- **Severity**: Critical
- **Auto-close**: 10 minutes after resolution

## Adding Notification Channels

To receive alerts, you need to create notification channels:

### Discord Webhook

1. Go to Cloud Console → Monitoring → Alerting → Notification channels
2. Click "Add New" → Webhook
3. Enter your Discord webhook URL
4. Save and note the channel ID

Then update the alert policies in `__main__.py`:

```python
error_rate_alert = gcp.monitoring.AlertPolicy(
    # ...existing config...
    notification_channels=[discord_webhook_channel.name],
)
```

### Email

1. Go to Cloud Console → Monitoring → Alerting → Notification channels
2. Click "Add New" → Email
3. Enter email addresses to notify

## Log-Based Metrics

The structured logging in `backend/services/structured_logging.py` outputs metrics as JSON log entries. You can create log-based metrics to track:

1. Go to Cloud Console → Logging → Log-based metrics
2. Create new metric with filter:

```
resource.type="cloud_run_revision"
resource.labels.service_name="karaoke-backend"
jsonPayload.metric_name="jobs_total"
```

3. Set extraction field to `jsonPayload.metric_value`

Repeat for other metrics:
- `worker_invocations_total`
- `job_stage_duration_seconds`
- `external_api_calls_total`
- `external_api_duration_seconds`
- `gcs_operations_total`

## Useful Log Queries

### Find all logs for a specific job:
```
resource.type="cloud_run_revision"
resource.labels.service_name="karaoke-backend"
jsonPayload.job_id="YOUR_JOB_ID"
```

### Find worker errors:
```
resource.type="cloud_run_revision"
resource.labels.service_name="karaoke-backend"
textPayload:"WORKER_END" AND textPayload:"status=error"
```

### Find slow workers (>5 min):
```
resource.type="cloud_run_revision"
resource.labels.service_name="karaoke-backend"
textPayload:"WORKER_END" AND textPayload:"duration=" 
```

Then add duration filter in the UI.

## Cloud Trace Integration

Structured logs include trace correlation fields:
- `logging.googleapis.com/trace`: Links to Cloud Trace
- `logging.googleapis.com/spanId`: Current span ID

To view correlated traces:
1. Find a log entry in Cloud Logging
2. Click the "View in Trace" link in the log entry
3. See the full distributed trace across services

