"""
Cloud Monitoring resources.

Manages alert policies for proactive monitoring and incident response.
"""

import pulumi
import pulumi_gcp as gcp


def create_alert_policies() -> dict[str, gcp.monitoring.AlertPolicy]:
    """
    Create all Cloud Monitoring alert policies.

    Returns:
        dict: Dictionary mapping alert names to AlertPolicy resources.
    """
    alerts = {}

    # Alert: High Error Rate (>10% of requests returning errors)
    alerts["error_rate"] = gcp.monitoring.AlertPolicy(
        "high-error-rate-alert",
        display_name="Karaoke Backend - High Error Rate",
        combiner="OR",
        conditions=[
            gcp.monitoring.AlertPolicyConditionArgs(
                display_name="Error rate > 10%",
                condition_threshold=gcp.monitoring.AlertPolicyConditionConditionThresholdArgs(
                    filter='resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend" AND metric.type="run.googleapis.com/request_count" AND metric.labels.response_code_class!="2xx"',
                    comparison="COMPARISON_GT",
                    threshold_value=0.1,
                    duration="300s",
                    aggregations=[
                        gcp.monitoring.AlertPolicyConditionConditionThresholdAggregationArgs(
                            alignment_period="60s",
                            per_series_aligner="ALIGN_RATE",
                            cross_series_reducer="REDUCE_SUM",
                        ),
                    ],
                    trigger=gcp.monitoring.AlertPolicyConditionConditionThresholdTriggerArgs(
                        count=1,
                    ),
                ),
            ),
        ],
        alert_strategy=gcp.monitoring.AlertPolicyAlertStrategyArgs(
            auto_close="3600s",
        ),
        documentation=gcp.monitoring.AlertPolicyDocumentationArgs(
            content="High error rate detected on karaoke-backend. Check Cloud Run logs for details.\n\nDashboard: https://console.cloud.google.com/run/detail/us-central1/karaoke-backend/logs?project=nomadkaraoke",
            mime_type="text/markdown",
        ),
        enabled=True,
    )

    # Alert: Cloud Tasks Queue Backlog (tasks piling up)
    alerts["queue_backlog"] = gcp.monitoring.AlertPolicy(
        "queue-backlog-alert",
        display_name="Karaoke Backend - Queue Backlog",
        combiner="OR",
        conditions=[
            gcp.monitoring.AlertPolicyConditionArgs(
                display_name="Queue depth > 50 tasks",
                condition_threshold=gcp.monitoring.AlertPolicyConditionConditionThresholdArgs(
                    filter='resource.type="cloud_tasks_queue" AND metric.type="cloudtasks.googleapis.com/queue/depth"',
                    comparison="COMPARISON_GT",
                    threshold_value=50,
                    duration="600s",
                    aggregations=[
                        gcp.monitoring.AlertPolicyConditionConditionThresholdAggregationArgs(
                            alignment_period="60s",
                            per_series_aligner="ALIGN_MEAN",
                            cross_series_reducer="REDUCE_MAX",
                        ),
                    ],
                    trigger=gcp.monitoring.AlertPolicyConditionConditionThresholdTriggerArgs(
                        count=1,
                    ),
                ),
            ),
        ],
        alert_strategy=gcp.monitoring.AlertPolicyAlertStrategyArgs(
            auto_close="1800s",
        ),
        documentation=gcp.monitoring.AlertPolicyDocumentationArgs(
            content="Cloud Tasks queue backlog detected. Tasks are piling up faster than workers can process.\n\nPossible causes:\n- Worker errors (check logs)\n- External API issues (Modal, AudioShake)\n- Cloud Run scaling limits\n\nDashboard: https://console.cloud.google.com/cloudtasks?project=nomadkaraoke",
            mime_type="text/markdown",
        ),
        enabled=True,
    )

    # Alert: High Memory Utilization (workers may be crashing)
    alerts["memory"] = gcp.monitoring.AlertPolicy(
        "high-memory-alert",
        display_name="Karaoke Backend - High Memory Usage",
        combiner="OR",
        conditions=[
            gcp.monitoring.AlertPolicyConditionArgs(
                display_name="Memory > 85%",
                condition_threshold=gcp.monitoring.AlertPolicyConditionConditionThresholdArgs(
                    filter='resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend" AND metric.type="run.googleapis.com/container/memory/utilizations"',
                    comparison="COMPARISON_GT",
                    threshold_value=0.85,
                    duration="300s",
                    aggregations=[
                        gcp.monitoring.AlertPolicyConditionConditionThresholdAggregationArgs(
                            alignment_period="60s",
                            per_series_aligner="ALIGN_PERCENTILE_95",
                            cross_series_reducer="REDUCE_MAX",
                        ),
                    ],
                    trigger=gcp.monitoring.AlertPolicyConditionConditionThresholdTriggerArgs(
                        count=1,
                    ),
                ),
            ),
        ],
        alert_strategy=gcp.monitoring.AlertPolicyAlertStrategyArgs(
            auto_close="1800s",
        ),
        documentation=gcp.monitoring.AlertPolicyDocumentationArgs(
            content="High memory utilization on karaoke-backend. Workers may be running out of memory.\n\nActions:\n- Check for memory leaks in worker code\n- Consider increasing Cloud Run memory limits\n- Review temp file cleanup",
            mime_type="text/markdown",
        ),
        enabled=True,
    )

    # Alert: Cloud Run Service Unavailable
    alerts["service_unavailable"] = gcp.monitoring.AlertPolicy(
        "service-unavailable-alert",
        display_name="Karaoke Backend - Service Unavailable",
        combiner="OR",
        conditions=[
            gcp.monitoring.AlertPolicyConditionArgs(
                display_name="No healthy instances",
                condition_absent=gcp.monitoring.AlertPolicyConditionConditionAbsentArgs(
                    filter='resource.type="cloud_run_revision" AND resource.labels.service_name="karaoke-backend" AND metric.type="run.googleapis.com/container/instance_count"',
                    duration="300s",
                    aggregations=[
                        gcp.monitoring.AlertPolicyConditionConditionAbsentAggregationArgs(
                            alignment_period="60s",
                            per_series_aligner="ALIGN_MEAN",
                            cross_series_reducer="REDUCE_SUM",
                        ),
                    ],
                ),
            ),
        ],
        alert_strategy=gcp.monitoring.AlertPolicyAlertStrategyArgs(
            auto_close="1800s",
        ),
        documentation=gcp.monitoring.AlertPolicyDocumentationArgs(
            content="Karaoke backend service appears to be down - no healthy Cloud Run instances detected.\n\nImmediate actions:\n1. Check Cloud Run logs for crash reasons\n2. Verify recent deployments\n3. Check external dependencies (Modal, AudioShake)\n\nService URL: https://api.nomadkaraoke.com/api/health",
            mime_type="text/markdown",
        ),
        enabled=True,
    )

    return alerts
