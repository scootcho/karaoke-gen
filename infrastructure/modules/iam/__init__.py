"""
IAM modules for service accounts and role bindings.

Organized by purpose:
- backend_sa: Main karaoke-backend service account
- github_actions_sa: GitHub Actions deployer with Workload Identity Federation
- claude_automation_sa: Claude Code automation service account
- worker_sas: Service accounts for VMs (flacfetch, encoding, gdrive, runners)
"""

from . import backend_sa
from . import github_actions_sa
from . import claude_automation_sa
from . import worker_sas

__all__ = [
    "backend_sa",
    "github_actions_sa",
    "claude_automation_sa",
    "worker_sas",
]
