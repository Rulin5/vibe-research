import re
from pathlib import Path

import pytest

from research.questions import RESEARCH_QUESTIONS
from research.policy import BASE_RESEARCH_POLICY
from research.router import InvalidResearchQuestionId, build_research_prompt, get_research_question


EXPECTED_IDS = {
    "recent_events",
    "latest_earnings",
    "growth_earnings",
    "expectations_gap",
    "valuation_framework",
    "business_model",
    "price_move_attribution",
    "earnings_quality",
    "cash_flow_capital_allocation",
    "industry_cycle",
    "competitive_value_capture",
    "risks_falsification",
}


def test_base_research_mode_uses_only_the_shared_policy():
    assert build_research_prompt(None) == BASE_RESEARCH_POLICY
    assert "只回答当前问题" in BASE_RESEARCH_POLICY
    assert "Point-in-Time" in BASE_RESEARCH_POLICY
    assert "估值 → 资金 → 财务 → 行业" not in BASE_RESEARCH_POLICY


def test_question_router_combines_base_policy_with_only_the_selected_prompt():
    business = build_research_prompt("business_model")
    growth = build_research_prompt("growth_earnings")

    assert business.startswith(BASE_RESEARCH_POLICY)
    assert "业务线 → 产品 / 服务 → 客户" in business
    assert "Revenue Drivers" not in business
    assert "Revenue Drivers" in growth
    assert "业务线 → 产品 / 服务 → 客户" not in growth


def test_invalid_question_id_fails_closed():
    with pytest.raises(InvalidResearchQuestionId):
        get_research_question("abc_not_exist")


def test_frontend_and_backend_question_ids_match_exactly():
    frontend = Path(__file__).parents[2] / "frontend" / "src" / "data" / "researchQuestions.ts"
    frontend_ids = set(re.findall(r'id: "([a-z_]+)"', frontend.read_text(encoding="utf-8")))

    assert set(RESEARCH_QUESTIONS) == EXPECTED_IDS
    assert frontend_ids == EXPECTED_IDS


def test_every_question_declares_a_real_data_capability_boundary():
    for question in RESEARCH_QUESTIONS.values():
        assert question.capability in {"FULLY_SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_SUPPORTED"}
        assert question.known_missing_data, question.id
