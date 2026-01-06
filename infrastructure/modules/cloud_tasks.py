"""
Cloud Tasks resources.

Manages task queues for asynchronous worker processing.
"""

import pulumi
import pulumi_gcp as gcp
from pulumi_gcp import cloudtasks

from config import REGION, QueueConfigs


def create_queues() -> dict[str, cloudtasks.Queue]:
    """
    Create all Cloud Tasks queues.

    These queues provide guaranteed delivery and horizontal scaling for worker tasks.
    Workers are triggered via Cloud Tasks instead of BackgroundTasks, ensuring:
    - Tasks survive container restarts
    - Each task gets dedicated resources
    - Automatic retries on failure
    - Rate limiting to protect external APIs

    Returns:
        dict: Dictionary mapping queue names to Queue resources.
    """
    queues = {}

    # Audio worker queue - calls Modal API for audio separation
    queues["audio-worker-queue"] = cloudtasks.Queue(
        "audio-worker-queue",
        name="audio-worker-queue",
        location=REGION,
        rate_limits=cloudtasks.QueueRateLimitsArgs(
            max_dispatches_per_second=QueueConfigs.Audio.MAX_DISPATCHES_PER_SECOND,
            max_concurrent_dispatches=QueueConfigs.Audio.MAX_CONCURRENT_DISPATCHES,
        ),
        retry_config=cloudtasks.QueueRetryConfigArgs(
            max_attempts=3,
            min_backoff="10s",
            max_backoff="300s",
            max_retry_duration=QueueConfigs.Audio.MAX_RETRY_DURATION,
        ),
    )

    # Lyrics worker queue - calls AudioShake API for transcription
    queues["lyrics-worker-queue"] = cloudtasks.Queue(
        "lyrics-worker-queue",
        name="lyrics-worker-queue",
        location=REGION,
        rate_limits=cloudtasks.QueueRateLimitsArgs(
            max_dispatches_per_second=QueueConfigs.Lyrics.MAX_DISPATCHES_PER_SECOND,
            max_concurrent_dispatches=QueueConfigs.Lyrics.MAX_CONCURRENT_DISPATCHES,
        ),
        retry_config=cloudtasks.QueueRetryConfigArgs(
            max_attempts=3,
            min_backoff="10s",
            max_backoff="300s",
            max_retry_duration=QueueConfigs.Lyrics.MAX_RETRY_DURATION,
        ),
    )

    # Screens worker queue - generates title/end screens (fast, CPU-light)
    queues["screens-worker-queue"] = cloudtasks.Queue(
        "screens-worker-queue",
        name="screens-worker-queue",
        location=REGION,
        rate_limits=cloudtasks.QueueRateLimitsArgs(
            max_dispatches_per_second=QueueConfigs.Screens.MAX_DISPATCHES_PER_SECOND,
            max_concurrent_dispatches=QueueConfigs.Screens.MAX_CONCURRENT_DISPATCHES,
        ),
        retry_config=cloudtasks.QueueRetryConfigArgs(
            max_attempts=3,
            min_backoff="5s",
            max_backoff="60s",
            max_retry_duration=QueueConfigs.Screens.MAX_RETRY_DURATION,
        ),
    )

    # Render worker queue - LyricsTranscriber + FFmpeg (CPU-intensive)
    queues["render-worker-queue"] = cloudtasks.Queue(
        "render-worker-queue",
        name="render-worker-queue",
        location=REGION,
        rate_limits=cloudtasks.QueueRateLimitsArgs(
            max_dispatches_per_second=QueueConfigs.Render.MAX_DISPATCHES_PER_SECOND,
            max_concurrent_dispatches=QueueConfigs.Render.MAX_CONCURRENT_DISPATCHES,
        ),
        retry_config=cloudtasks.QueueRetryConfigArgs(
            max_attempts=2,
            min_backoff="30s",
            max_backoff="300s",
            max_retry_duration=QueueConfigs.Render.MAX_RETRY_DURATION,
        ),
    )

    # Video worker queue - final encoding (very CPU-intensive, longest running)
    queues["video-worker-queue"] = cloudtasks.Queue(
        "video-worker-queue",
        name="video-worker-queue",
        location=REGION,
        rate_limits=cloudtasks.QueueRateLimitsArgs(
            max_dispatches_per_second=QueueConfigs.Video.MAX_DISPATCHES_PER_SECOND,
            max_concurrent_dispatches=QueueConfigs.Video.MAX_CONCURRENT_DISPATCHES,
        ),
        retry_config=cloudtasks.QueueRetryConfigArgs(
            max_attempts=2,
            min_backoff="60s",
            max_backoff="600s",
            max_retry_duration=QueueConfigs.Video.MAX_RETRY_DURATION,
        ),
    )

    # Idle reminder queue - delayed tasks for sending reminder emails
    # Tasks are scheduled with a 5-minute delay when jobs enter blocking states
    queues["idle-reminder-queue"] = cloudtasks.Queue(
        "idle-reminder-queue",
        name="idle-reminder-queue",
        location=REGION,
        rate_limits=cloudtasks.QueueRateLimitsArgs(
            max_dispatches_per_second=10,   # Email sending is fast
            max_concurrent_dispatches=50,
        ),
        retry_config=cloudtasks.QueueRetryConfigArgs(
            max_attempts=3,
            min_backoff="10s",
            max_backoff="60s",
            max_retry_duration="600s",      # 10 min total
        ),
    )

    return queues
