"""/github routes: who may call them and what they return; the work happens in services/github.py."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from backend.core.security import require_admin, require_cron
from backend.dependencies import github_profile_service
from backend.models.github import GitHubResult, PublishRequest
from backend.services.github import GitHubProfileService

router = APIRouter(prefix="/github")
Service = Annotated[GitHubProfileService, Depends(github_profile_service)]
# Leaves out targets the call did not touch, and fields a change has no value for
RESULT = {"response_model": GitHubResult, "response_model_exclude_none": True}


@router.post("/publish", dependencies=[Depends(require_admin)], **RESULT)
async def publish(body: PublishRequest, service: Service) -> GitHubResult:
    """Admin only: commits the README (skipped when unchanged) and/or updates the profile details."""
    return await service.publish(body)


@router.get("/refresh", dependencies=[Depends(require_cron)], **RESULT)
async def refresh(service: Service) -> GitHubResult:
    """Daily (vercel.json): recomputes the experience durations in the published README and bio."""
    return await service.refresh(date.today())
