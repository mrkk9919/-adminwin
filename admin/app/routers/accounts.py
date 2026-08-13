"""Accounts router — list, filter, freeze/unfreeze bank accounts.

Shows one row per customer with combined KHR + USD balances,
using customers table as the source of truth.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app import auth, database

router = APIRouter(prefix="/accounts",
                   dependencies=[Depends(auth.require_admin)])
_templates = Jinja2Templates(directory=str(
    Path(__file__).resolve().parent.parent / "templates"))


def _normalize_customer_record(row: dict) -> dict:
    """Map customer data to the fields used by the account templates."""
    record = dict(row)
    record["customer_status"] = record.get("role") or record.get("customer_status") or "customer"
    record["balance_khr"] = int(record.get("balance_khr") or 0)
    record["balance_usd"] = int(record.get("balance_usd") or 0)
    record["kyc_status"] = record.get("kyc_status") or "pending"
    record["status"] = record["customer_status"]
    return record


def _list_accounts(
    currency: str = "",
    acct_status: str = "",
    q: str = "",
    page: int = 1,
    limit: int = 20,
) -> tuple[list[dict], int]:
    """One row per customer with account info from the shared customer + accounts tables."""
    where_clauses = []
    params: list = []

    if q.strip():
        like = f"%{q.strip()}%"
        where_clauses.append(
            "(c.username LIKE ? OR CAST(c.telegram_id AS TEXT) LIKE ? "
            "OR c.first_name LIKE ? OR c.last_name LIKE ? OR c.phone LIKE ?)"
        )
        params.extend([like] * 5)

    if acct_status:
        if acct_status == "active":
            where_clauses.append("c.is_active = 1 AND c.role != 'banned'")
        elif acct_status == "suspended":
            where_clauses.append("c.is_active = 0 OR c.role = 'banned'")
        else:
            where_clauses.append("c.role = ?")
            params.append(acct_status)

    where = " AND ".join(where_clauses) if where_clauses else "1=1"
    offset = (page - 1) * limit

    with database.get_conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM customers c WHERE {where}",
            params,
        ).fetchone()[0]

        rows = conn.execute(
            f"""
            SELECT
              c.telegram_id,
              c.first_name,
              c.last_name,
              c.username,
              c.phone,
              c.role,
              c.is_active,
              c.created_at,
              c.updated_at,
              COALESCE((SELECT SUM(a.balance) FROM accounts a WHERE a.customer_id = c.telegram_id AND a.currency = 'KHR'), 0) AS balance_khr,
              COALESCE((SELECT SUM(a.balance) FROM accounts a WHERE a.customer_id = c.telegram_id AND a.currency = 'USD'), 0) AS balance_usd,
              COALESCE((SELECT k.status FROM kyc_records k WHERE k.customer_id = c.telegram_id ORDER BY k.submitted_at DESC LIMIT 1), 'pending') AS kyc_status,
              (SELECT COUNT(*) FROM accounts a WHERE a.customer_id = c.telegram_id AND a.status = 'active') AS active_acct_count,
              (SELECT COUNT(*) FROM accounts a WHERE a.customer_id = c.telegram_id AND a.status = 'frozen') AS frozen_acct_count,
              (SELECT COUNT(*) FROM accounts a WHERE a.customer_id = c.telegram_id) AS total_acct_count,
              (SELECT GROUP_CONCAT(a.account_number, ', ') FROM accounts a WHERE a.customer_id = c.telegram_id) AS account_numbers
            FROM customers c
            WHERE {where}
            ORDER BY c.updated_at DESC LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

    return [_normalize_customer_record(dict(r)) for r in rows], total


@router.get("")
def accounts_list(
    request: Request,
    currency: str = "",
    status: str = "",
    q: str = "",
    page: int = 1,
    username: str = Depends(auth.require_admin),
):
    accounts, total = _list_accounts(currency, status, q, page)
    return _templates.TemplateResponse(
        "accounts/list.html",
        {
            "request": request,
            "username": username,
            "active": "accounts",
            "accounts": accounts,
            "total": total,
            "currency": currency,
            "status_filter": status,
            "q": q,
            "page": page,
            "pages": max(1, (total + 19) // 20),
        },
    )


@router.get("/{telegram_id}")
def account_detail(
    request: Request,
    telegram_id: int,
    username: str = Depends(auth.require_admin),
):
    """Show all accounts for a specific customer and allow profile edits from the Accounts screen."""
    customer = database.fetchone(
        "SELECT * FROM customers WHERE telegram_id = ?",
        (telegram_id,),
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = _normalize_customer_record(dict(customer))
    customer["kyc_status"] = database.fetchone(
        "SELECT status FROM kyc_records WHERE customer_id = ? ORDER BY submitted_at DESC LIMIT 1",
        (telegram_id,),
    )
    customer["kyc_status"] = (customer["kyc_status"]["status"] if customer["kyc_status"] else "pending")
    customer["balance_khr"] = database.fetchone(
        "SELECT COALESCE(SUM(balance), 0) AS total FROM accounts WHERE customer_id = ? AND currency = 'KHR'",
        (telegram_id,),
    )["total"]
    customer["balance_usd"] = database.fetchone(
        "SELECT COALESCE(SUM(balance), 0) AS total FROM accounts WHERE customer_id = ? AND currency = 'USD'",
        (telegram_id,),
    )["total"]

    accounts = [
        dict(r) for r in database.fetchall(
            "SELECT * FROM accounts WHERE customer_id = ? ORDER BY currency",
            (telegram_id,),
        )
    ]

    txns = []
    for a in accounts:
        rows = database.fetchall(
            "SELECT t.*, a2.account_number AS other_account "
            "FROM transactions t "
            "LEFT JOIN accounts a2 ON a2.id = (CASE WHEN t.from_account_id = ? THEN t.to_account_id ELSE t.from_account_id END) "
            "WHERE t.from_account_id = ? OR t.to_account_id = ? "
            "ORDER BY t.created_at DESC LIMIT 10",
            (a["id"], a["id"], a["id"]),
        )
        for r in rows:
            d = dict(r)
            d["account_currency"] = a["currency"]
            d["direction"] = "in" if d.get("to_account_id") == a["id"] else "out"
            txns.append(d)

    txns.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    txns = txns[:20]

    return _templates.TemplateResponse(
        "accounts/detail.html",
        {
            "request": request,
            "username": username,
            "active": "accounts",
            "customer": customer,
            "accounts": accounts,
            "transactions": txns,
        },
    )


@router.post("/{telegram_id}/edit")
def account_edit(
    telegram_id: int,
    role: str = Form(...),
    is_active: str = Form("1"),
    phone: str = Form(""),
    notes: str = Form(""),
    _username: str = Depends(auth.require_admin),
):
    active = 1 if is_active in ("1", "on", "true") else 0
    database.execute(
        "UPDATE customers SET role = ?, is_active = ?, phone = ?, notes = ?, "
        "updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
        (role, active, phone, notes, telegram_id),
    )
    return RedirectResponse(
        url=f"/accounts/{telegram_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{telegram_id}/create-account")
def create_account(
    telegram_id: int,
    account_number: str = Form(...),
    currency: str = Form("KHR"),
    account_type: str = Form("wallet"),
    balance: str = Form("0"),
    status: str = Form("active"),
    _username: str = Depends(auth.require_admin),
):
    """Create a bank/wallet account for an existing customer."""
    customer = database.fetchone(
        "SELECT telegram_id FROM customers WHERE telegram_id = ?",
        (telegram_id,),
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    account_number = (account_number or "").strip()
    if not account_number:
        raise HTTPException(status_code=400, detail="Account number is required")

    currency = (currency or "KHR").upper()
    if currency not in {"KHR", "USD"}:
        raise HTTPException(status_code=400, detail="Currency must be KHR or USD")

    account_type = (account_type or "wallet").strip() or "wallet"
    status = (status or "active").strip() or "active"

    try:
        balance_value = int(float(balance)) if balance not in (None, "") else 0
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Balance must be a number") from exc

    try:
        database.execute(
            """
            INSERT INTO accounts (
                customer_id, account_number, currency, balance, status, type,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (telegram_id, account_number, currency, balance_value, status, account_type),
        )
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=400,
            detail="Account number already exists or is invalid.",
        ) from exc

    return RedirectResponse(
        url=f"/accounts/{telegram_id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{account_id}/freeze")
def account_freeze(account_id: int, _username: str = Depends(auth.require_admin)):
    database.execute(
        "UPDATE accounts SET status = 'frozen', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (account_id,),
    )
    return RedirectResponse(url=f"/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{account_id}/unfreeze")
def account_unfreeze(account_id: int, _username: str = Depends(auth.require_admin)):
    database.execute(
        "UPDATE accounts SET status = 'active', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (account_id,),
    )
    return RedirectResponse(url=f"/accounts", status_code=status.HTTP_303_SEE_OTHER)
