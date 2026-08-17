export type ResearchQuestionGroup = "primary" | "advanced";

export interface ResearchQuestion {
  id: string;
  label: string;
  group: ResearchQuestionGroup;
}

export const RESEARCH_QUESTIONS: ResearchQuestion[] = [
  { id: "recent_events", label: "最近发生了什么？", group: "primary" },
  { id: "latest_earnings", label: "最新财报验证了什么？", group: "primary" },
  { id: "growth_earnings", label: "增长与利润弹性", group: "primary" },
  { id: "expectations_gap", label: "市场预期与预期差", group: "primary" },
  { id: "valuation_framework", label: "估值与定价框架", group: "primary" },
  { id: "business_model", label: "公司怎么赚钱？", group: "primary" },
  { id: "price_move_attribution", label: "近期异动归因", group: "advanced" },
  { id: "earnings_quality", label: "盈利质量", group: "advanced" },
  { id: "cash_flow_capital_allocation", label: "现金流与资本配置", group: "advanced" },
  { id: "industry_cycle", label: "行业景气与周期", group: "advanced" },
  { id: "competitive_value_capture", label: "竞争格局与价值捕获", group: "advanced" },
  { id: "risks_falsification", label: "风险与证伪", group: "advanced" },
];
