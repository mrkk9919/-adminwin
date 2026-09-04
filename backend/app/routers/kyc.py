"""KYC router — review queue, approve/reject workflow."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database

router = APIRouter(prefix="/kyc", dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))


@router.get("")
def kyc_list(
    request: Request,
    status: str = "",
    page: int = 1,
    username: str = Depends(auth.require_admin),
):
    where_clauses = []
    params: list = []
    if status:
        where_clauses.append("k.status = ?")
        params.append(status)

    where = " AND ".join(where_clauses) if where_clauses else "1=1"
    limit = 20
    offset = (page - 1) * limit

    with database.get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM kyc_records k WHERE {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT k.*, c.first_name, c.last_name, c.username, c.phone "
            f"FROM kyc_records k "
            f"LEFT JOIN customers c ON c.telegram_id = k.customer_id "
            f"WHERE {where} ORDER BY k.submitted_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        all_count = conn.execute(
            "SELECT COUNT(*) FROM kyc_records").fetchone()[0]

    return _templates.TemplateResponse(
        "kyc/list.html",
        {
            "request": request,
            "username": username,
            "active": "kyc",
            "records": [dict(r) for r in rows],
            "total": total,
            "status_filter": status,
            "page": page,
            "pages": max(1, (total + limit - 1) // limit),
            "all_count": all_count,
        },
    )


@router.get("/{kyc_id}")
def kyc_detail(
    request: Request,
    kyc_id: int,
    username: str = Depends(auth.require_admin),
):
    record = database.fetchone(
        "SELECT k.*, c.first_name, c.last_name, c.username, c.phone, c.email "
        "FROM kyc_records k LEFT JOIN customers c ON c.telegram_id = k.customer_id "
        "WHERE k.id = ?",
        (kyc_id,),
    )
    if not record:
        raise HTTPException(status_code=404, detail="KYC record not found")

    return _templates.TemplateResponse(
        "kyc/detail.html",
        {
            "request": request,
            "username": username,
            "active": "kyc",
            "record": dict(record),
        },
    )


@router.post("/{kyc_id}/approve")
def kyc_approve(
    kyc_id: int,
    reviewer: str = Form("admin"),
    _username: str = Depends(auth.require_admin),
):
    with database.get_conn() as conn:
        record = conn.execute(
            "SELECT customer_id FROM kyc_records WHERE id = ?", (kyc_id,)).fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="KYC record not found")
        conn.execute(
            "UPDATE kyc_records SET status = 'approved', reviewed_at = datetime('now', '+7 hours'), "
            "reviewed_by = ? WHERE id = ?",
            (reviewer, kyc_id),
        )
        conn.execute(
            "UPDATE customers SET kyc_status = 'approved', updated_at = datetime('now', '+7 hours') "
            "WHERE telegram_id = ?",
            (record["customer_id"],),
        )
    return RedirectResponse(url=f"/kyc/{kyc_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{kyc_id}/reject")
def kyc_reject(
    kyc_id: int,
    reason: str = Form(...),
    reviewer: str = Form("admin"),
    _username: str = Depends(auth.require_admin),
):
    with database.get_conn() as conn:
        record = conn.execute(
            "SELECT customer_id FROM kyc_records WHERE id = ?", (kyc_id,)).fetchone()
        if not record:
            raise HTTPException(status_code=404, detail="KYC record not found")
        conn.execute(
            "UPDATE kyc_records SET status = 'rejected', reviewed_at = datetime('now', '+7 hours'), "
            "reviewed_by = ?, rejection_reason = ? WHERE id = ?",
            (reviewer, reason, kyc_id),
        )
        conn.execute(
            "UPDATE customers SET kyc_status = 'rejected', updated_at = datetime('now', '+7 hours') "
            "WHERE telegram_id = ?",
            (record["customer_id"],),
        )
    return RedirectResponse(url=f"/kyc/{kyc_id}", status_code=status.HTTP_303_SEE_OTHER)
