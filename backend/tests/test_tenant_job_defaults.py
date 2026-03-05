"""
Unit tests for tenant-aware job defaults and distribution overrides.

Tests that:
- Tenant config fields (brand_prefix, dropbox_path, gdrive_folder_id) are applied to jobs
- All tenant jobs are forced private
- Locked theme overrides user selection
- Private tenant jobs use tenant-specific paths (not NonPublished)
- Non-tenant private jobs still use NonPublished paths
"""

import pytest
from unittest.mock import MagicMock, patch

from backend.models.tenant import TenantConfig, TenantDefaults, TenantFeatures, TenantBranding, TenantAuth
from backend.services.job_defaults_service import (
    get_effective_distribution_settings,
    get_effective_distribution_for_job,
    EffectiveDistributionSettings,
)


def _make_tenant_config(**defaults_kwargs) -> TenantConfig:
    """Create a TenantConfig with custom defaults for testing."""
    return TenantConfig(
        id="vocalstar",
        name="Vocal Star",
        subdomain="vocalstar.nomadkaraoke.com",
        defaults=TenantDefaults(
            locked_theme="vocalstar",
            distribution_mode="cloud_only",
            brand_prefix="VSTAR",
            dropbox_path="/Karaoke/Vocal-Star",
            gdrive_folder_id="gdrive-folder-123",
            **defaults_kwargs,
        ),
    )


def _make_job_mock(**kwargs):
    """Create a mock job object with the given attributes."""
    defaults = {
        "is_private": False,
        "tenant_id": None,
        "dropbox_path": None,
        "gdrive_folder_id": None,
        "brand_prefix": None,
        "enable_youtube_upload": False,
        "discord_webhook_url": None,
        "youtube_description_template": None,
    }
    defaults.update(kwargs)
    job = MagicMock()
    for key, value in defaults.items():
        setattr(job, key, value)
    return job


class TestApplyTenantOverrides:
    """Tests for _apply_tenant_overrides() in file_upload.py."""

    def _get_apply_fn(self):
        """Import the function under test."""
        from backend.api.routes.file_upload import _apply_tenant_overrides
        return _apply_tenant_overrides

    def test_tenant_defaults_applied_to_distribution(self):
        """Tenant brand_prefix, dropbox_path, gdrive_folder_id are applied to distribution settings."""
        apply_fn = self._get_apply_fn()
        tenant_config = _make_tenant_config()

        dist = EffectiveDistributionSettings(
            dropbox_path=None,
            gdrive_folder_id=None,
            discord_webhook_url=None,
            brand_prefix=None,
            enable_youtube_upload=True,
            youtube_description=None,
        )

        new_dist, theme, is_private, yt_upload = apply_fn(
            dist, tenant_config, "default", False, True
        )

        assert new_dist.brand_prefix == "VSTAR"
        assert new_dist.dropbox_path == "/Karaoke/Vocal-Star"
        assert new_dist.gdrive_folder_id == "gdrive-folder-123"

    def test_tenant_job_forced_private(self):
        """All tenant jobs are forced to is_private=True."""
        apply_fn = self._get_apply_fn()
        tenant_config = _make_tenant_config()

        dist = EffectiveDistributionSettings(
            dropbox_path=None, gdrive_folder_id=None, discord_webhook_url=None,
            brand_prefix=None, enable_youtube_upload=True, youtube_description=None,
        )

        _, _, is_private, _ = apply_fn(dist, tenant_config, "default", False, True)
        assert is_private is True

    def test_tenant_locked_theme_applied(self):
        """locked_theme overrides the user's theme selection."""
        apply_fn = self._get_apply_fn()
        tenant_config = _make_tenant_config()

        dist = EffectiveDistributionSettings(
            dropbox_path=None, gdrive_folder_id=None, discord_webhook_url=None,
            brand_prefix=None, enable_youtube_upload=True, youtube_description=None,
        )

        _, theme, _, _ = apply_fn(dist, tenant_config, "user-selected-theme", False, True)
        assert theme == "vocalstar"

    def test_tenant_youtube_upload_disabled(self):
        """YouTube upload is disabled for tenant jobs."""
        apply_fn = self._get_apply_fn()
        tenant_config = _make_tenant_config()

        dist = EffectiveDistributionSettings(
            dropbox_path=None, gdrive_folder_id=None, discord_webhook_url=None,
            brand_prefix=None, enable_youtube_upload=True, youtube_description=None,
        )

        _, _, _, yt_upload = apply_fn(dist, tenant_config, "default", False, True)
        assert yt_upload is False

    def test_request_values_take_precedence(self):
        """Explicit request-level values are not overridden by tenant defaults."""
        apply_fn = self._get_apply_fn()
        tenant_config = _make_tenant_config()

        dist = EffectiveDistributionSettings(
            dropbox_path="/Custom/Path",
            gdrive_folder_id="custom-folder",
            discord_webhook_url=None,
            brand_prefix="CUSTOM",
            enable_youtube_upload=True,
            youtube_description=None,
        )

        new_dist, _, _, _ = apply_fn(dist, tenant_config, "default", False, True)
        assert new_dist.brand_prefix == "CUSTOM"
        assert new_dist.dropbox_path == "/Custom/Path"
        assert new_dist.gdrive_folder_id == "custom-folder"

    def test_no_tenant_config_passthrough(self):
        """When no tenant config, all values pass through unchanged."""
        apply_fn = self._get_apply_fn()

        dist = EffectiveDistributionSettings(
            dropbox_path="/Some/Path", gdrive_folder_id=None, discord_webhook_url=None,
            brand_prefix="NOMAD", enable_youtube_upload=True, youtube_description=None,
        )

        new_dist, theme, is_private, yt_upload = apply_fn(
            dist, None, "nomad", False, True
        )
        assert new_dist.brand_prefix == "NOMAD"
        assert new_dist.dropbox_path == "/Some/Path"
        assert theme == "nomad"
        assert is_private is False
        assert yt_upload is True


class TestTenantJobDistribution:
    """Tests for get_effective_distribution_for_job() with tenant jobs."""

    def test_private_tenant_job_uses_tenant_paths(self):
        """Private tenant jobs use their own Dropbox/GDrive paths, not NonPublished."""
        job = _make_job_mock(
            is_private=True,
            tenant_id="vocalstar",
            dropbox_path="/Karaoke/Vocal-Star",
            gdrive_folder_id="gdrive-folder-123",
            brand_prefix="VSTAR",
        )

        result = get_effective_distribution_for_job(job)

        assert result.dropbox_path == "/Karaoke/Vocal-Star"
        assert result.gdrive_folder_id == "gdrive-folder-123"
        assert result.brand_prefix == "VSTAR"
        assert result.enable_youtube_upload is False

    @patch("backend.services.job_defaults_service.get_settings")
    def test_non_tenant_private_job_still_uses_nonpublished(self, mock_settings):
        """Non-tenant private jobs still get the NonPublished path override."""
        mock_settings.return_value = MagicMock(
            default_private_dropbox_path="/Tracks-NonPublished",
            default_private_brand_prefix="NOMADNP",
        )

        job = _make_job_mock(
            is_private=True,
            tenant_id=None,
            dropbox_path="/Some/User/Path",
            brand_prefix="SOMETHING",
        )

        result = get_effective_distribution_for_job(job)

        assert result.dropbox_path == "/Tracks-NonPublished"
        assert result.brand_prefix == "NOMADNP"
        assert result.enable_youtube_upload is False
        assert result.gdrive_folder_id is None

    def test_non_private_job_uses_own_settings(self):
        """Non-private jobs (tenant or not) use their own distribution settings."""
        job = _make_job_mock(
            is_private=False,
            tenant_id="vocalstar",
            dropbox_path="/Karaoke/Vocal-Star",
            gdrive_folder_id="gdrive-folder-123",
            brand_prefix="VSTAR",
            enable_youtube_upload=False,
        )

        result = get_effective_distribution_for_job(job)

        assert result.dropbox_path == "/Karaoke/Vocal-Star"
        assert result.gdrive_folder_id == "gdrive-folder-123"
        assert result.brand_prefix == "VSTAR"
