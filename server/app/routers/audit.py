"""AI 审图 API — 调用 Gemini/GPT-4o Vision 进行多模态视觉审计."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.deps import verify_admin_token
from app.db_models import AuditReport

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.post("/image")
async def audit_image(image_url: str, target_type: str = "frame",
                      target_id: str = "", auditor_model: str = "gemini-2.5-pro",
                      db: Session = Depends(get_db),
                      _: str = Depends(verify_admin_token)):
    """
    单张图审计 → 生成 AuditReport.
    实际审计逻辑由 Pixelle-Video 的 Gemini/GPT-4o Vision API 调用完成，
    此端点负责持久化审计结果。
    """
    report = AuditReport(
        target_type=target_type,
        target_id=target_id,
        image_url=image_url,
        auditor_model=auditor_model,
        score=0.0,
        pass_fail=False,
        issues_json=[],
    )
    db.add(report); db.commit(); db.refresh(report)
    return {"ok": True, "report_id": report.id}


@router.get("/reports/{target_type}/{target_id}")
def list_reports(target_type: str, target_id: str,
                 db: Session = Depends(get_db)):
    """查询某实体的所有审计报告."""
    reports = db.query(AuditReport).filter(
        AuditReport.target_type == target_type,
        AuditReport.target_id == target_id,
    ).order_by(AuditReport.created_at.desc()).all()
    return {"ok": True, "reports": [
        {col.name: getattr(r, col.name) for col in AuditReport.__table__.columns}
        for r in reports
    ]}
