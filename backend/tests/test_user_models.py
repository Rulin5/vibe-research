from __future__ import annotations

from decimal import Decimal

import pytest

from models import ClosedPosition, PortfolioHolding, ResearchNote, User, WatchlistItem, normalize_security


def test_normalize_security_accepts_only_six_digit_a_share_codes():
    assert normalize_security(" 600519 ") == ("CN", "600519")
    with pytest.raises(ValueError, match="6 位"):
        normalize_security("60051")
    with pytest.raises(ValueError, match="数字"):
        normalize_security("6005AA")


def test_private_records_are_distinguished_by_user_id():
    first = User(id="user-a", username="alpha", password_hash="hash-a")
    second = User(id="user-b", username="beta", password_hash="hash-b")

    first_watch = WatchlistItem(user_id=first.id, market="CN", code="600519")
    second_watch = WatchlistItem(user_id=second.id, market="CN", code="600519")
    holding = PortfolioHolding(
        user_id=first.id,
        market="CN",
        code="600519",
        shares=Decimal("100"),
        cost=Decimal("1420.50"),
    )
    closed = ClosedPosition(
        user_id=first.id,
        market="CN",
        code="600519",
        closed_on="2026-08-11",
        price=Decimal("1430.00"),
        shares=Decimal("100"),
        cost=Decimal("1420.50"),
    )
    note = ResearchNote(user_id=first.id, title="复盘", content="仅用户 A 可见")

    assert first_watch.user_id != second_watch.user_id
    assert holding.user_id == closed.user_id == note.user_id == first.id
    assert holding.shares == Decimal("100")
    assert holding.cost == Decimal("1420.50")
