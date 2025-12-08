"""
Pulumi infrastructure for Karaoke Generator backend on Google Cloud Platform.

This replaces the manual setup scripts with proper Infrastructure as Code.
"""
import pulumi
import pulumi_gcp as gcp
from pulumi_gcp import storage, firestore, secretmanager, artifactregistry, cloudrun, serviceaccount

# Get the current GCP project
project = gcp.organizations.get_project()
project_id = project.project_id

# Create Firestore Database
firestore_db = firestore.Database(
    "karaoke-firestore",
    project=project_id,
    name="(default)",
    location_id="us-central1",
    type="FIRESTORE_NATIVE",
    concurrency_mode="PESSIMISTIC",
    app_engine_integration_mode="DISABLED",
)

# Create Cloud Storage Bucket
bucket = storage.Bucket(
    "karaoke-storage",
    name=f"karaoke-gen-storage-{project_id}",
    location="US-CENTRAL1",
    force_destroy=False,  # Prevent accidental deletion
    uniform_bucket_level_access=True,
    lifecycle_rules=[
        storage.BucketLifecycleRuleArgs(
            action=storage.BucketLifecycleRuleActionArgs(type="Delete"),
            condition=storage.BucketLifecycleRuleConditionArgs(
                age=7,
                matches_prefixes=["temp/", "uploads/"]
            ),
        ),
    ],
)

# Create Artifact Registry Repository for Docker images
artifact_repo = artifactregistry.Repository(
    "karaoke-artifact-repo",
    repository_id="karaoke-repo",
    location="us-central1",
    format="DOCKER",
    description="Docker repository for karaoke backend images",
)

# Create Service Account for Cloud Run
service_account = serviceaccount.Account(
    "karaoke-backend-sa",
    account_id="karaoke-backend",
    display_name="Karaoke Backend Service Account",
)

# Grant Firestore permissions
firestore_iam = gcp.projects.IAMMember(
    "karaoke-backend-firestore-access",
    project=project_id,
    role="roles/datastore.user",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Storage permissions
storage_iam = gcp.projects.IAMMember(
    "karaoke-backend-storage-access",
    project=project_id,
    role="roles/storage.objectAdmin",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Secret Manager permissions
secrets_iam = gcp.projects.IAMMember(
    "karaoke-backend-secrets-access",
    project=project_id,
    role="roles/secretmanager.secretAccessor",
    member=service_account.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Cloud Build service accounts access to Artifact Registry
# Cloud Build uses multiple service accounts depending on the context
cloudbuild_service_accounts = [
    f"serviceAccount:{project.number}@cloudbuild.gserviceaccount.com",  # Default Cloud Build SA
    f"serviceAccount:service-{project.number}@gcp-sa-cloudbuild.iam.gserviceaccount.com",  # Cloud Build service agent
    f"serviceAccount:{project.number}-compute@developer.gserviceaccount.com",  # Compute service account
]

artifact_registry_iam = artifactregistry.RepositoryIamBinding(
    "cloudbuild-artifact-registry-access",
    repository=artifact_repo.name,
    location=artifact_repo.location,
    role="roles/artifactregistry.writer",
    members=cloudbuild_service_accounts,
)

# Grant Cloud Build compute service account logging permissions
# This fixes the "does not have permission to write logs" warning
cloudbuild_logging_iam = gcp.projects.IAMMember(
    "cloudbuild-logging-access",
    project=project_id,
    role="roles/logging.logWriter",
    member=f"serviceAccount:{project.number}-compute@developer.gserviceaccount.com",
)

# ==================== GitHub Actions Deployer Service Account ====================
# This service account is used by GitHub Actions CI/CD via Workload Identity Federation

github_actions_sa = serviceaccount.Account(
    "github-actions-deployer-sa",
    account_id="github-actions-deployer",
    display_name="GitHub Actions Deployer",
    description="Service account for GitHub Actions CD via Workload Identity",
)

# Grant Cloud Run admin permissions
github_actions_run_admin = gcp.projects.IAMMember(
    "github-actions-run-admin",
    project=project_id,
    role="roles/run.admin",
    member=github_actions_sa.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant service account user permissions (to deploy Cloud Run with other SA)
github_actions_sa_user = gcp.projects.IAMMember(
    "github-actions-sa-user",
    project=project_id,
    role="roles/iam.serviceAccountUser",
    member=github_actions_sa.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Artifact Registry writer permissions
github_actions_artifact_writer = gcp.projects.IAMMember(
    "github-actions-artifact-writer",
    project=project_id,
    role="roles/artifactregistry.writer",
    member=github_actions_sa.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Cloud Build permissions - REQUIRED for gcloud builds submit
github_actions_cloudbuild = gcp.projects.IAMMember(
    "github-actions-cloudbuild",
    project=project_id,
    role="roles/cloudbuild.builds.editor",
    member=github_actions_sa.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Storage Admin for Cloud Build bucket uploads
github_actions_storage = gcp.projects.IAMMember(
    "github-actions-storage-admin",
    project=project_id,
    role="roles/storage.admin",
    member=github_actions_sa.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Logging write permissions for Cloud Build logs
github_actions_logging = gcp.projects.IAMMember(
    "github-actions-logging",
    project=project_id,
    role="roles/logging.logWriter",
    member=github_actions_sa.email.apply(lambda email: f"serviceAccount:{email}"),
)

# Grant Service Usage Consumer - required for serviceusage.services.use permission
github_actions_service_usage = gcp.projects.IAMMember(
    "github-actions-service-usage",
    project=project_id,
    role="roles/serviceusage.serviceUsageConsumer",
    member=github_actions_sa.email.apply(lambda email: f"serviceAccount:{email}"),
)

# ==================== Workload Identity Federation ====================
# Allows GitHub Actions to authenticate without service account keys

workload_identity_pool = gcp.iam.WorkloadIdentityPool(
    "github-actions-pool",
    workload_identity_pool_id="github-actions-pool",
    display_name="GitHub Actions Pool",
    description="Workload Identity Pool for GitHub Actions",
    disabled=False,
)

workload_identity_provider = gcp.iam.WorkloadIdentityPoolProvider(
    "github-actions-provider",
    workload_identity_pool_id=workload_identity_pool.workload_identity_pool_id,
    workload_identity_pool_provider_id="github-actions-provider",
    display_name="GitHub Actions Provider",
    attribute_mapping={
        "google.subject": "assertion.sub",
        "attribute.actor": "assertion.actor",
        "attribute.repository": "assertion.repository",
        "attribute.repository_owner": "assertion.repository_owner",
    },
    attribute_condition="assertion.repository_owner == 'nomadkaraoke'",
    oidc=gcp.iam.WorkloadIdentityPoolProviderOidcArgs(
        issuer_uri="https://token.actions.githubusercontent.com",
    ),
)

# Allow GitHub Actions to impersonate the service account
github_actions_wif_binding = gcp.serviceaccount.IAMBinding(
    "github-actions-wif-binding",
    service_account_id=github_actions_sa.name,
    role="roles/iam.workloadIdentityUser",
    members=[workload_identity_pool.name.apply(
        lambda pool_name: f"principalSet://iam.googleapis.com/{pool_name}/attribute.repository/nomadkaraoke/karaoke-gen"
    )],
)

# Create secrets (you'll need to add the actual secret values manually or via pulumi config)
config = pulumi.Config()

# AudioShake API Key Secret
audioshake_secret = secretmanager.Secret(
    "audioshake-api-key",
    secret_id="audioshake-api-key",
    replication=secretmanager.SecretReplicationArgs(
        auto=secretmanager.SecretReplicationAutoArgs(),
    ),
)

# Genius API Key Secret
genius_secret = secretmanager.Secret(
    "genius-api-key",
    secret_id="genius-api-key",
    replication=secretmanager.SecretReplicationArgs(
        auto=secretmanager.SecretReplicationAutoArgs(),
    ),
)

# Audio Separator API URL Secret
audio_separator_secret = secretmanager.Secret(
    "audio-separator-api-url",
    secret_id="audio-separator-api-url",
    replication=secretmanager.SecretReplicationArgs(
        auto=secretmanager.SecretReplicationAutoArgs(),
    ),
)

# Create Cloud Run Domain Mapping
# Maps api.nomadkaraoke.com to the karaoke-backend service
domain_mapping = cloudrun.DomainMapping(
    "karaoke-backend-domain",
    location="us-central1",
    name="api.nomadkaraoke.com",
    metadata=cloudrun.DomainMappingMetadataArgs(
        namespace=project_id,
    ),
    spec=cloudrun.DomainMappingSpecArgs(
        route_name="karaoke-backend",
    ),
)

# Export important values
pulumi.export("project_id", project_id)
pulumi.export("bucket_name", bucket.name)
pulumi.export("firestore_database", firestore_db.name)
pulumi.export("service_account_email", service_account.email)
pulumi.export("artifact_repo_url", artifact_repo.name.apply(
    lambda name: f"us-central1-docker.pkg.dev/{project_id}/karaoke-repo"
))
pulumi.export("backend_url", "https://api.nomadkaraoke.com")
pulumi.export("backend_default_url", "https://karaoke-backend-ipzqd2k4yq-uc.a.run.app")

# GitHub Actions CD exports
pulumi.export("github_actions_service_account", github_actions_sa.email)
pulumi.export("workload_identity_provider", workload_identity_provider.name)

# Export DNS configuration needed for Cloudflare
# These are the records to add to your Cloudflare DNS
domain_mapping.statuses.apply(
    lambda statuses: pulumi.export("dns_records", {
        "type": "CNAME",
        "name": "api",
        "value": "ghs.googlehosted.com",
        "ttl": 300,
        "proxied": False  # Must be false for Cloud Run domain verification
    })
)

