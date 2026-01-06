"""
Cloud Run resources.

Manages Cloud Run domain mapping and Cloud Run Jobs.
"""

import pulumi
import pulumi_gcp as gcp
from pulumi_gcp import cloudrun, cloudrunv2

from config import PROJECT_ID, REGION


def create_domain_mapping() -> cloudrun.DomainMapping:
    """
    Create the Cloud Run domain mapping for api.nomadkaraoke.com.

    Returns:
        cloudrun.DomainMapping: The domain mapping resource.
    """
    domain_mapping = cloudrun.DomainMapping(
        "karaoke-backend-domain",
        location=REGION,
        name="api.nomadkaraoke.com",
        metadata=cloudrun.DomainMappingMetadataArgs(
            namespace=PROJECT_ID,
        ),
        spec=cloudrun.DomainMappingSpecArgs(
            route_name="karaoke-backend",
        ),
    )

    return domain_mapping


def create_video_encoding_job(
    bucket: gcp.storage.Bucket,
    service_account: gcp.serviceaccount.Account,
) -> cloudrunv2.Job:
    """
    Create the Cloud Run Job for video encoding.

    Cloud Run Jobs provide up to 24-hour execution time for long-running video encoding.
    This is used when video encoding might exceed the 30-minute Cloud Tasks timeout.

    Args:
        bucket: The GCS bucket for job artifacts.
        service_account: The service account to run the job.

    Returns:
        cloudrunv2.Job: The Cloud Run Job resource.
    """
    video_encoding_job = cloudrunv2.Job(
        "video-encoding-job",
        name="video-encoding-job",
        location=REGION,
        template=cloudrunv2.JobTemplateArgs(
            template=cloudrunv2.JobTemplateTemplateArgs(
                containers=[
                    cloudrunv2.JobTemplateTemplateContainerArgs(
                        image=f"{REGION}-docker.pkg.dev/{PROJECT_ID}/karaoke-repo/karaoke-backend:latest",
                        args=["python", "-m", "backend.workers.video_worker"],
                        resources=cloudrunv2.JobTemplateTemplateContainerResourcesArgs(
                            limits={
                                "cpu": "4",
                                "memory": "8Gi",
                            },
                        ),
                        envs=[
                            cloudrunv2.JobTemplateTemplateContainerEnvArgs(
                                name="GOOGLE_CLOUD_PROJECT",
                                value=PROJECT_ID,
                            ),
                            cloudrunv2.JobTemplateTemplateContainerEnvArgs(
                                name="GCS_BUCKET_NAME",
                                value=bucket.name,
                            ),
                        ],
                    )
                ],
                service_account=service_account.email,
                timeout="3600s",  # 1 hour max per task
                max_retries=2,
            ),
        ),
    )

    return video_encoding_job
