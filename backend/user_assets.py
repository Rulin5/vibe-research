"""Database services for authenticated, user-owned investment records."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

import astock
from models import ClosedPosition, PortfolioHolding, ResearchNote, User, WatchlistItem, normalize_security


def _decimal(value: float | int | str) -> Decimal:
    return Decimal(str(value))


def _as_number(value: Decimal) -> float:
    return float(value)


def _security(code: str) -> tuple[str, str]:
    try:
        return normalize_security(code)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


def _watch_row(item: WatchlistItem) -> dict:
    return {"id": item.id, "market": item.market, "code": item.code, "created_at": item.created_at.isoformat()}


def list_watchlist(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(WatchlistItem).where(WatchlistItem.user_id == user.id).order_by(WatchlistItem.created_at.desc())
    ).scalars()
    return [_watch_row(item) for item in rows]


def add_watchlist_item(db: Session, user: User, code: str) -> tuple[dict, bool]:
    market, normalized = _security(code)
    item = db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user.id, WatchlistItem.market == market, WatchlistItem.code == normalized
        )
    ).scalar_one_or_none()
    if item is not None:
        return _watch_row(item), False
    item = WatchlistItem(user_id=user.id, market=market, code=normalized)
    db.add(item)
    db.commit()
    db.refresh(item)
    return _watch_row(item), True


def delete_watchlist_item(db: Session, user: User, item_id: str) -> None:
    item = db.execute(
        select(WatchlistItem).where(WatchlistItem.id == item_id, WatchlistItem.user_id == user.id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "自选股不存在")
    db.delete(item)
    db.commit()


def _holding_row(item: PortfolioHolding, quote: dict | None, quote_status: str) -> dict:
    cost = _as_number(item.cost)
    shares = _as_number(item.shares)
    raw_price = quote.get("price") if quote else None
    try:
        price = float(raw_price) if raw_price is not None else None
    except (TypeError, ValueError):
        price = None
    if price is None:
        quote_status = "quote_missing" if quote_status == "available" else quote_status
    market_value = price * shares if price is not None else None
    pnl = market_value - cost * shares if market_value is not None else None
    return {
        "id": item.id,
        "market": item.market,
        "code": item.code,
        "name": str(quote.get("name") or item.code) if quote else item.code,
        "price": price,
        "shares": shares,
        "cost": cost,
        "market_value": market_value,
        "pnl": pnl,
        "pnl_pct": pnl / (cost * shares) * 100 if pnl is not None and cost and shares else None,
        "quote_status": quote_status,
    }


def _closed_row(item: ClosedPosition) -> dict:
    price = _as_number(item.price)
    cost = _as_number(item.cost)
    shares = _as_number(item.shares)
    pnl = (price - cost) * shares
    return {
        "id": item.id,
        "market": item.market,
        "code": item.code,
        "name": item.code,
        "date": item.closed_on.isoformat(),
        "price": price,
        "shares": shares,
        "cost": cost,
        "pnl": pnl,
        "pnl_pct": (price - cost) / cost * 100 if cost else None,
    }


def portfolio_payload(db: Session, user: User) -> dict:
    holdings = list(
        db.execute(
            select(PortfolioHolding).where(PortfolioHolding.user_id == user.id).order_by(PortfolioHolding.created_at.desc())
        ).scalars()
    )
    closed = list(
        db.execute(
            select(ClosedPosition).where(ClosedPosition.user_id == user.id).order_by(ClosedPosition.closed_on.desc())
        ).scalars()
    )
    queried_at = None
    quotes: dict[str, dict] = {}
    quote_status = "available"
    if holdings:
        queried_at = datetime.now(timezone.utc).isoformat()
        try:
            quotes = astock.tencent_quote(sorted({item.code for item in holdings}))
        except Exception:  # The payload exposes the source failure instead of fabricating a price.
            quote_status = "source_unavailable"

    holding_rows = [_holding_row(item, quotes.get(item.code), quote_status) for item in holdings]
    quotes_complete = bool(holding_rows) and all(item["quote_status"] == "available" for item in holding_rows)
    total_cost = sum(_as_number(item.cost * item.shares) for item in holdings)
    total_market_value = sum(item["market_value"] for item in holding_rows) if quotes_complete else None
    total_pnl = total_market_value - total_cost if total_market_value is not None else None
    closed_rows = [_closed_row(item) for item in closed]
    return {
        "holdings": holding_rows,
        "totals": {
            "market_value": total_market_value,
            "cost": total_cost,
            "pnl": total_pnl,
            "pnl_pct": total_pnl / total_cost * 100 if total_pnl is not None and total_cost else None,
        },
        "closed": closed_rows,
        "realized_pnl": sum(item["pnl"] for item in closed_rows),
        "updated": datetime.now(timezone.utc).isoformat(),
        "last_refresh": queried_at,
    }


def add_holding(db: Session, user: User, code: str, shares: float, cost: float) -> dict:
    market, normalized = _security(code)
    if shares <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "数量必须大于 0")
    item = PortfolioHolding(user_id=user.id, market=market, code=normalized, shares=_decimal(shares), cost=_decimal(cost))
    db.add(item)
    db.commit()
    db.refresh(item)
    return _holding_row(item, None, "unavailable")


def delete_holding(db: Session, user: User, holding_id: str) -> None:
    item = db.execute(
        select(PortfolioHolding).where(PortfolioHolding.id == holding_id, PortfolioHolding.user_id == user.id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "持仓不存在")
    db.delete(item)
    db.commit()


def add_closed_position(db: Session, user: User, code: str, closed_on: date, price: float, shares: float, cost: float) -> dict:
    market, normalized = _security(code)
    if price <= 0 or shares <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "清仓价和数量必须大于 0")
    item = ClosedPosition(
        user_id=user.id,
        market=market,
        code=normalized,
        closed_on=closed_on,
        price=_decimal(price),
        shares=_decimal(shares),
        cost=_decimal(cost),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _closed_row(item)


def delete_closed_position(db: Session, user: User, position_id: str) -> None:
    item = db.execute(
        select(ClosedPosition).where(ClosedPosition.id == position_id, ClosedPosition.user_id == user.id)
    ).scalar_one_or_none()
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "已清仓记录不存在")
    db.delete(item)
    db.commit()


def list_notes(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(ResearchNote).where(ResearchNote.user_id == user.id).order_by(ResearchNote.updated_at.desc())
    ).scalars()
    return [
        {
            "id": note.id,
            "kind": note.kind,
            "title": note.title,
            "content": note.content,
            "created_at": note.created_at.isoformat(),
            "updated_at": note.updated_at.isoformat(),
        }
        for note in rows
    ]


def create_note(db: Session, user: User, kind: str, title: str, content: str) -> dict:
    if not (title or "").strip() or not (content or "").strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "标题和内容不能为空")
    normalized_kind = (kind or "general").strip()[:64] or "general"
    note = ResearchNote(user_id=user.id, kind=normalized_kind, title=title.strip()[:255], content=content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "id": note.id,
        "kind": note.kind,
        "title": note.title,
        "content": note.content,
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat(),
    }


def delete_note(db: Session, user: User, note_id: str) -> None:
    note = db.execute(select(ResearchNote).where(ResearchNote.id == note_id, ResearchNote.user_id == user.id)).scalar_one_or_none()
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "研究记录不存在")
    db.delete(note)
    db.commit()
