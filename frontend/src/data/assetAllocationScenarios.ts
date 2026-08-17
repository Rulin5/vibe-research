export type AllocationSlice = {
  id: "liquidity" | "fixed-income" | "equity" | "diversifier";
  label: string;
  description: string;
  percentage: number;
  exampleAmount: number;
  color: string;
};

export type AssetAllocationScenario = {
  id: "under-100k" | "100k-to-500k" | "500k-to-2m" | "over-2m";
  assetBandLabel: string;
  stageLabel: string;
  exampleTotal: number;
  riskLabel: string;
  allocation: AllocationSlice[];
};

export const ASSET_ALLOCATION_SCENARIOS: AssetAllocationScenario[] = [
  {
    id: "under-100k",
    assetBandLabel: "10 万元以下",
    stageLabel: "先把生活与应急底座打稳",
    exampleTotal: 50_000,
    riskLabel: "极低风险示例",
    allocation: [
      { id: "liquidity", label: "流动性储备", description: "日常支出、紧急备用金和等待机会的流动性空间。", percentage: 70, exampleAmount: 35_000, color: "#3b82f6" },
      { id: "fixed-income", label: "低波动固收", description: "用于降低整体波动的稳定层，不等同于保本承诺。", percentage: 20, exampleAmount: 10_000, color: "#14b8a6" },
      { id: "equity", label: "宽基权益", description: "仅以长期闲置资金承担分散化的权益波动。", percentage: 5, exampleAmount: 2_500, color: "#38bdf8" },
      { id: "diversifier", label: "黄金及低相关资产", description: "作为少量不同风险来源的补充，而非收益承诺。", percentage: 5, exampleAmount: 2_500, color: "#8b5cf6" },
    ],
  },
  {
    id: "100k-to-500k",
    assetBandLabel: "10–50 万元",
    stageLabel: "先分开管理近期与长期资金",
    exampleTotal: 300_000,
    riskLabel: "低风险示例",
    allocation: [
      { id: "liquidity", label: "流动性储备", description: "为生活支出和短期安排预留充足的缓冲空间。", percentage: 55, exampleAmount: 165_000, color: "#3b82f6" },
      { id: "fixed-income", label: "低波动固收", description: "承担组合稳定层的角色，重视期限和风险匹配。", percentage: 30, exampleAmount: 90_000, color: "#14b8a6" },
      { id: "equity", label: "宽基权益", description: "只放入可长期持有、能接受阶段性波动的资金。", percentage: 10, exampleAmount: 30_000, color: "#38bdf8" },
      { id: "diversifier", label: "黄金及低相关资产", description: "以小比例增加资产来源的分散性。", percentage: 5, exampleAmount: 15_000, color: "#8b5cf6" },
    ],
  },
  {
    id: "500k-to-2m",
    assetBandLabel: "50–200 万元",
    stageLabel: "建立稳定层后再做适度分散",
    exampleTotal: 1_000_000,
    riskLabel: "保守配置示例",
    allocation: [
      { id: "liquidity", label: "流动性储备", description: "覆盖预期支出和突发情况，避免短期资金承担市场波动。", percentage: 45, exampleAmount: 450_000, color: "#3b82f6" },
      { id: "fixed-income", label: "低波动固收", description: "作为组合的主要稳定层，优先关注风险和期限匹配。", percentage: 35, exampleAmount: 350_000, color: "#14b8a6" },
      { id: "equity", label: "宽基权益", description: "以高度分散的长期权益敞口保留有限增长空间。", percentage: 15, exampleAmount: 150_000, color: "#38bdf8" },
      { id: "diversifier", label: "黄金及低相关资产", description: "以少量配置分散单一风险来源。", percentage: 5, exampleAmount: 50_000, color: "#8b5cf6" },
    ],
  },
  {
    id: "over-2m",
    assetBandLabel: "200 万元以上",
    stageLabel: "先控制集中度，再增加资产分散",
    exampleTotal: 3_000_000,
    riskLabel: "保守家庭资产示例",
    allocation: [
      { id: "liquidity", label: "流动性储备", description: "为家庭现金流、突发支出和机会成本保留弹性。", percentage: 35, exampleAmount: 1_050_000, color: "#3b82f6" },
      { id: "fixed-income", label: "低波动固收", description: "继续承担稳定层角色，避免把稳定性简单理解为收益率。", percentage: 40, exampleAmount: 1_200_000, color: "#14b8a6" },
      { id: "equity", label: "宽基权益", description: "保留受限的长期权益比例，避免单一市场或行业集中。", percentage: 20, exampleAmount: 600_000, color: "#38bdf8" },
      { id: "diversifier", label: "黄金及低相关资产", description: "少量补充不同风险来源，不作为保本或短期交易工具。", percentage: 5, exampleAmount: 150_000, color: "#8b5cf6" },
    ],
  },
];

export function formatExampleCny(amount: number) {
  return `¥${amount.toLocaleString("zh-CN")}`;
}
