"""Whitelisted question-specific prompts for Research Mode."""

from typing import NamedTuple


class ResearchQuestion(NamedTuple):
    id: str
    label: str
    prompt: str
    capability: str = "PARTIALLY_SUPPORTED"
    known_missing_data: tuple[str, ...] = ()
    requires_point_in_time: bool = False


_QUESTIONS = (
    ResearchQuestion("recent_events", "最近发生了什么？", """【当前问题：Incremental Evidence Scan】
检查公司自最近一个有效研究节点以来的新增重要信息，优先公司公告、财报/预告/快报、订单合同、产品技术、客户、产能、并购投资、回购减持、管理层、监管、行业价格库存、下游CapEx和政策；不要做普通新闻聚合。
每条重要信息说明“事件 → 日期 → 证据等级 → 影响的经营变量 → 研究价值”。有历史 Research Snapshot 才可判断增强、削弱、暂不改变或待验证；没有历史 Thesis/Snapshot 时，不得声称改变了用户原投资逻辑，只执行 Event Scan → Driver Mapping → Research Relevance。"""),
    ResearchQuestion("latest_earnings", "最新财报验证了什么？", """【当前问题：Change Detection + Driver Validation】
分析最新财报相对此前经营认知新增了什么，不复述整份财报，优先找3–6个重要变化变量。有历史 Driver Tree 才判断验证、未验证和反证；否则只做 Change Detection，不伪造此前投资逻辑。
A股累计数据须按 Q2=H1-Q1、Q3=9M-H1、Q4=FY-9M 重构单季度；数据不足时说明限制，禁止把H1累计与Q1累计当普通环比。重点观察单季度收入、扣非利润、毛利率、现金流、应收、存货、合同负债、CapEx、研发、减值和债务。"""),
    ResearchQuestion("growth_earnings", "增长与利润弹性", """【当前问题：Revenue Driver + Earnings Bridge】
先按商业模式识别 Revenue Equation，不得把所有公司统一简化为销量×ASP：制造业看需求、份额、销量、ASP、结构和产能；SaaS看客户数、ARPU、留存/扩张率；银行看生息资产、净息差、非息收入和信用成本；资源看产量、商品价格和单位成本；消费看销量、价格、结构和渠道；医药看患者、渗透率和单患者价值。
再建立 Revenue → Gross Profit → EBIT → Pre-tax Profit → Recurring Net Profit 的 Earnings Bridge，识别毛利率、费用率、利用率、规模效应、汇兑、减值和税率。回答 Revenue Drivers、Earnings Drivers、Operating Leverage、Growth Bottleneck、Next Validation Metrics；规划和券商预测不得写成已实现增长。"""),
    ResearchQuestion("expectations_gap", "市场预期与预期差", """【当前问题：Expectations Gap】
比较实际收入、利润、EPS、毛利率与事件发生前最后一个有效一致预期快照及管理层指引，并观察分析师数量、中位数、离散度和预测修正。严格遵守 Point-in-Time，禁止用财报发布后修正的一致预期反推 Beat/In-line/Miss。
若只有最新一致预期而没有事件前快照，必须明确写：“当前缺少事件发生前 Point-in-Time Consensus，无法严谨判断本次结果是否超预期或低于预期。”可以描述当前预期，但不得伪造历史预期差。""",
        "NOT_SUPPORTED", ("事件发生前一致预期快照", "预测修订历史", "预测离散度"), True),
    ResearchQuestion("valuation_framework", "估值与定价框架", """【当前问题：Valuation Regime Selection】
先按公司类型选择框架：普通盈利制造/消费用PE、EV/EBITDA、FCF Yield；银行用PB、ROE和信用成本；保险用P/EV、NBV；周期资源用Mid-cycle Earnings、EV/EBITDA、PB；SaaS用EV/Sales、Growth、Margin；多业务集团用SOTP；创新药用Pipeline/rNPV。禁止所有公司统一使用PE/PB/PS。
再比较 Current Valuation → Historical Range → Peer Valuation → Fundamental Consistency，说明合适方法、历史位置、真正可比公司、溢折价支撑和承压变量。历史分位高低不等于必然贵贱；无Reverse Valuation数据时不得声称精确隐含增长率。"""),
    ResearchQuestion("business_model", "公司怎么赚钱？", """【当前问题：Business Model Decomposition】
按照“业务线 → 产品 / 服务 → 客户 → 定价 / 收费方式 → 收入池 → 毛利池 → 经营利润池 → 资本占用 → 经济价值来源”拆解。披露到哪一级就分析到哪一级：分业务收入、分业务毛利、分部经营利润、分部资本占用/ROIC。
未披露分业务经营利润或资本占用时明确无法验证，禁止自行分摊总部费用、研发、固定资产或资本占用。回答最大收入池、最大毛利池、可验证的主要利润池、最资本密集业务及最可能创造长期经济价值的业务。"""),
    ResearchQuestion("price_move_attribution", "近期异动归因", """【当前问题：Price Move Attribution】
先判断是否存在显著相对异动，分别比较 Stock Return-Benchmark Return 与 Stock Return-Industry Return，禁止把市场和行业收益简单重复扣除。再检查成交额、换手率、波动、公告、财报、行业事件、政策和重要新闻。
输出区分市场因素、行业因素、公司特异性因素和无法确认部分。新闻与股价同日出现不能直接建立因果；Residual/abnormal return只说明存在基准无法解释的变化，不能自动归因某一公司事件。"""),
    ResearchQuestion("earnings_quality", "盈利质量", """【当前问题：Earnings Quality】
沿 Reported Earnings → Recurring Earnings → Cash Conversion → Working Capital → Impairment → One-offs → Sustainability 判断利润是否有经营和现金支撑。检查扣非/归母、OCF/净利润、FCF、应收和存货相对收入、合同资产/负债、减值、非经常损益、补助、公允价值变动、研发资本化。
ROE/ROIC仅作辅助。回答现金支撑、营运资金、一次性项目、利润现金背离和缺失数据；数据不足时明确只能有限判断。"""),
    ResearchQuestion("cash_flow_capital_allocation", "现金流与资本配置", """【当前问题：Funding Capacity + Capital Allocation Quality】
分成两个子问题。A Funding Capacity：检查OCF、FCF、现金、净债务、短债、债务到期、利息、营运资金、CapEx和Committed CapEx，判断是否能维持经营扩张。B Capital Allocation Quality：检查维持/成长CapEx、并购、分红、回购、还债、股权融资和历史扩产回报。
账面现金多不等于现金流充足，当前FCF负不等于资本配置差；区分高回报扩张与低回报资本消耗。无法判断未来CapEx义务或历史ROIC时说明证据不足。"""),
    ResearchQuestion("industry_cycle", "行业景气与周期", """【当前问题：Industry Cycle】
区分 Structural Trend、Demand Cycle、Inventory Cycle、Pricing Cycle、Capacity Cycle，不把长期结构成长直接写成当前景气。沿终端需求 → 下游销量/CapEx → 订单 → 库存 → 产能利用率 → 供需 → 价格 → 公司销量/ASP/毛利研究，并寻找Backlog、开工/稼动率、新增/在建产能、交付周期和竞争者扩产。
行业指数、成交、资金和估值只属于 Market Pricing Evidence，不能证明 Industry Fundamentals。缺少产业经营数据时明确证据覆盖不足。"""),
    ResearchQuestion("competitive_value_capture", "竞争格局与价值捕获", """【当前问题：Competitive Positioning + Value Capture】
先识别行业真正的 Key Success Factors，选择决定胜负的5–8个变量和2–4家业务真正可比的竞争者，不按行业分类强行比较。分析客户/供应商议价、切换成本、标准化、壁垒、替代品、产能稀缺、成本转嫁和定价权。
回答行业比什么、公司领先项、最大短板、真实定价权、产业增长中可转为公司利润的价值以及最可能改变份额和利润的竞争变量；缺少业务可比数据时明确说明。"""),
    ResearchQuestion("risks_falsification", "风险与证伪", """【当前问题：Thesis Falsification】
先判断 Thesis 来源。有用户确认Thesis才使用；否则必须标记：“以下为系统根据当前公开证据归纳的候选经营逻辑，并非用户已确认的投资判断。”区分 Thesis Risk、Financial Risk、Market Risk、Governance/Event Risk，只有Thesis Risk主要用于证伪经营逻辑。
每条核心逻辑按 Thesis → Supporting Evidence → Key Driver → Leading Indicator → Counter Evidence → Weakening Condition → Falsification Condition 展开。证伪条件尽量可观察、可更新、可量化、有来源和时间窗，禁止用“竞争加剧”“宏观经济恶化”等泛风险作为最终证伪条件。"""),
)

_MISSING_DATA = {
    "recent_events": ("公告/新闻/研报正文", "历史Research Snapshot"),
    "latest_earnings": ("多期财务明细", "单季度重构字段", "营运资本与减值明细"),
    "growth_earnings": ("分业务量价", "费用率与产能利用率", "完整利润桥"),
    "valuation_framework": ("EV/EBITDA与FCF Yield", "SOTP/rNPV", "严格可比公司数据"),
    "business_model": ("分业务收入与毛利", "分部经营利润", "资本占用与ROIC"),
    "price_move_attribution": ("同期基准和行业完整收益序列", "事件正文与严格事件窗口"),
    "earnings_quality": ("完整现金流量表", "应收存货和减值明细", "非经常项目明细"),
    "cash_flow_capital_allocation": ("FCF与债务期限", "CapEx与并购回报", "Committed CapEx"),
    "industry_cycle": ("行业需求库存价格", "产能利用率与订单", "竞争者扩产数据"),
    "competitive_value_capture": ("公司级同业经营KPI", "市场份额与成本曲线", "定价权证据"),
    "risks_falsification": ("用户确认Thesis", "历史Research Snapshot", "领先指标序列"),
}

RESEARCH_QUESTIONS = {
    question.id: question._replace(known_missing_data=_MISSING_DATA.get(question.id, question.known_missing_data))
    for question in _QUESTIONS
}
