"""Deterministic, fail-closed Research Mode prompt router."""

from research.policy import BASE_RESEARCH_POLICY
from research.questions import RESEARCH_QUESTIONS, ResearchQuestion


class InvalidResearchQuestionId(ValueError):
    """Raised when the client supplies an ID outside the server registry."""


def get_research_question(question_id: str) -> ResearchQuestion:
    try:
        return RESEARCH_QUESTIONS[question_id]
    except KeyError as exc:
        raise InvalidResearchQuestionId(question_id) from exc


def build_research_prompt(question_id: str | None) -> str:
    if question_id is None:
        return BASE_RESEARCH_POLICY
    question = get_research_question(question_id)
    missing = "\n".join(f"- {item}" for item in question.known_missing_data) or "- 当前工具未声明额外缺失项"
    boundary = f"""【当前数据能力边界】
当前能力状态：{question.capability}
已知缺失：
{missing}
只能基于可获得证据回答，禁止补造缺失经营指标，不得基于缺失字段生成确定性结论。"""
    if question.requires_point_in_time:
        boundary += "\n当前缺少事件发生前一致预期快照。禁止判断 Beat / In-line / Miss / 超预期 / 低于预期，除非工具明确返回事件前快照。"
    return f"{BASE_RESEARCH_POLICY}\n\n{question.prompt}\n\n{boundary}"
