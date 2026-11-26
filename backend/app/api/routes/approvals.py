"""Human-in-the-loop approval and safe tool execution audit endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.approvals.service import ApprovalError, ApprovalService, serialize_approval
from app.config import Settings, get_settings
from app.database.database import get_db
from app.database.models import User
from app.database.repositories import ApprovalRepository, ToolExecutionRepository
from app.schemas.approval import ApprovalDecisionResponse, ApprovalListResponse, ApprovalOut
from app.schemas.chat import ToolExecutionListResponse, ToolExecutionLogOut
from app.security.auth import get_current_user, sensitive_rate_limiter

router = APIRouter(tags=["Approvals & Activity"])


def get_approval_service(settings: Settings = Depends(get_settings)) -> ApprovalService:
    return ApprovalService(settings=settings)


@router.get("/approvals", response_model=ApprovalListResponse)
def list_approvals(
    approval_status: str | None = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApprovalListResponse:
    """List approval requests belonging strictly to the authenticated user."""
    repo = ApprovalRepository(db, user_id=current_user.id)
    items = repo.list_all(status=approval_status)
    all_pending = repo.list_all(status="PENDING")
    return ApprovalListResponse(
        approvals=[serialize_approval(item) for item in items],
        pending_count=len(all_pending),
    )


@router.get("/approvals/{approval_id}", response_model=ApprovalOut)
def get_approval(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApprovalOut:
    """Get details of one approval owned by the authenticated user."""
    item = ApprovalRepository(db, user_id=current_user.id).get_by_id(approval_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval {approval_id} was not found.",
        )
    return serialize_approval(item)


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalDecisionResponse)
def approve_action(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalDecisionResponse:
    """Approve and execute a PENDING action using its immutable stored payload."""
    sensitive_rate_limiter.check(f"approve:{current_user.id}")
    try:
        updated = service.approve_and_execute(db, user=current_user, approval_id=approval_id)
    except ApprovalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    msg = (
        "Action approved and executed."
        if updated.status == "EXECUTED"
        else f"Action approved, but execution ended with status '{updated.status}'."
    )
    return ApprovalDecisionResponse(approval=updated, message=msg)


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalDecisionResponse)
def reject_action(
    approval_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: ApprovalService = Depends(get_approval_service),
) -> ApprovalDecisionResponse:
    """Reject a PENDING approval owned by the authenticated user."""
    try:
        updated = service.reject(db, user_id=current_user.id, approval_id=approval_id)
    except ApprovalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return ApprovalDecisionResponse(approval=updated, message="Action rejected.")


@router.get("/tool-executions", response_model=ToolExecutionListResponse)
def list_tool_executions(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ToolExecutionListResponse:
    """Return safe tool activity logs (no tokens or sensitive email bodies)."""
    rows = ToolExecutionRepository(db, user_id=current_user.id).list_recent(limit=limit)
    return ToolExecutionListResponse(
        executions=[ToolExecutionLogOut.model_validate(r) for r in rows],
        count=len(rows),
    )
