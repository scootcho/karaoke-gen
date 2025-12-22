"""
Minimal test to verify our auth mocking approach works.
"""
import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from backend.services.auth_service import UserType


def test_auth_override_approach():
    """Test that dependency override works for auth."""
    from backend.main import app
    from backend.api.dependencies import require_auth
    
    # Create a mock auth function
    async def mock_auth(*args, **kwargs):
        return ("test-token", UserType.ADMIN, 999)
    
    # Override the dependency
    app.dependency_overrides[require_auth] = mock_auth
    
    client = TestClient(app)
    
    try:
        # Test an authenticated endpoint
        response = client.get("/api/jobs")
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:200]}")
        
        # Should succeed (200 or other valid response), not 401
        assert response.status_code != 401, "Auth should be mocked"
        
    finally:
        # Clean up
        app.dependency_overrides.clear()


if __name__ == "__main__":
    test_auth_override_approach()

