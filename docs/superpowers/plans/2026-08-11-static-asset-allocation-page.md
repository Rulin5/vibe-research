# Static Asset Allocation Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a polished, standalone “资产配置” page that lets a visitor switch between four total-financial-asset bands and inspect a deliberately conservative, static allocation example for each band.

**Architecture:** This is a frontend-only educational page. A typed local scenario dataset supplies all displayed amounts and percentages; the React page owns only the selected-band UI state. It will not read portfolios, quotes, accounts, AI settings, APIs, or databases. Routing and the existing application navigation expose the page without creating any data linkage.

**Tech Stack:** React 18, TypeScript, React Router, Tailwind CSS, lucide-react, existing `PageHeader` / `GlassCard` visual primitives, Node built-in test runner, Vite.

## Scope and financial-content boundaries

- The page is a **static allocation example**, not a personalised recommendation, current market analysis, expected-return projection, product solicitation, or trading signal.
- It will display a persistent Chinese disclaimer: “本页为静态教育性资产配置示例，不构成投资建议；请结合负债、现金流、期限、风险承受能力和适当性要求独立决策。”
- No data may be labelled “实时”, “今日”, “市场数据”, or imply it came from the existing financial data supplier.
- No individual stocks, fund codes, fund names, yields, prices, historical returns, Sharpe ratios, or unverified performance claims will be shown.
- The four buckets use only broad asset classes: `流动性储备`、`低波动固收`、`宽基权益`、`黄金及低相关资产`.
- The figures are fixed examples rather than a calculator: selecting a tier changes to that tier’s pre-authored illustrative total and allocation amounts. No user asset value is collected, stored, or transmitted.
- The page remains independent from login data and personal holdings. It may be publicly routable, consistent with the existing market/research pages; it must not query private state.

## Static scenario contract

Each scenario must sum to 100% and have an internally consistent example amount. The intentionally conservative baseline is:

| Total financial assets band | Displayed illustrative total | Liquidity reserve | Low-volatility fixed income | Broad-market equity | Gold / low-correlation assets |
| --- | ---: | ---: | ---: | ---: | ---: |
| Below ¥100,000 | ¥50,000 | 70% / ¥35,000 | 20% / ¥10,000 | 5% / ¥2,500 | 5% / ¥2,500 |
| ¥100,000–¥500,000 | ¥300,000 | 55% / ¥165,000 | 30% / ¥90,000 | 10% / ¥30,000 | 5% / ¥15,000 |
| ¥500,000–¥2,000,000 | ¥1,000,000 | 45% / ¥450,000 | 35% / ¥350,000 | 15% / ¥150,000 | 5% / ¥50,000 |
| Above ¥2,000,000 | ¥3,000,000 | 35% / ¥1,050,000 | 40% / ¥1,200,000 | 20% / ¥600,000 | 5% / ¥150,000 |

Supporting text must make the assumptions explicit:

- Higher-interest debt, essential insurance gaps, and a 6–12 month emergency reserve are handled before allocating risk assets.
- No leverage, no concentration in a single security/industry, and no short-term chasing of market moves are assumed.
- The “review rule” is an educational prompt only: revisit on an annual cadence or when an allocation materially drifts; it is not an automated rebalance instruction.

## File map

| File | Change |
| --- | --- |
| `frontend/src/data/assetAllocationScenarios.ts` | New typed, local-only scenario contract and the four fixed scenarios. |
| `frontend/src/pages/AssetAllocation.tsx` | New static interactive UI; only local selected-tier state. |
| `frontend/src/router.tsx` | Register the `/asset-allocation` route. |
| `frontend/src/components/layout/Layout.tsx` | Add an “资产配置” navigation item. |
| `frontend/tests/asset-allocation-contract.test.mjs` | New source-level regression test for static-data, disclaimer, route, and no-linkage guarantees. |

## Implementation tasks

### Task 1: Define the local, auditable static-data contract

**Files:**
- Create: `frontend/src/data/assetAllocationScenarios.ts`
- Create: `frontend/tests/asset-allocation-contract.test.mjs`

- [x] Introduce explicit types so that each displayed number has a business meaning and cannot silently become a market-data field:

```ts
export type AllocationSlice = {
  id: 'liquidity' | 'fixed-income' | 'equity' | 'diversifier'
  label: string
  description: string
  percentage: number
  exampleAmount: number
  color: string
}

export type AssetAllocationScenario = {
  id: 'under-100k' | '100k-to-500k' | '500k-to-2m' | 'over-2m'
  assetBandLabel: string
  exampleTotal: number
  riskLabel: string
  allocation: AllocationSlice[]
}
```

- [x] Encode exactly the four scenarios in the table above. Keep example amounts as integers in yuan and calculate no values from external inputs.
- [x] Give each asset-class description plain-language scope only, for example “日常支出、紧急备用金和等待机会的流动性空间”; do not name securities or products.
- [x] Add small pure helpers only if the page needs them, such as `formatCnyCompact(amount)`. Do not add network clients, persistence helpers, or financial calculation utilities.
- [x] Write a Node contract test that reads the TypeScript/page/router/layout source and asserts:
  - all four tier IDs and all four asset-class IDs are present;
  - the permanent educational disclaimer exists;
  - the page does not use `api.`, `fetch(`, `useWatchlist`, `useAuth`, `chatStream`, or portfolio hooks;
  - the route and navigation destination are `/asset-allocation`.

### Task 2: Build the standalone asset-allocation experience

**Files:**
- Create: `frontend/src/pages/AssetAllocation.tsx`

- [x] Use only `useState` to set a default selected scenario (`500k-to-2m`) and switch it when the user clicks a tier card. Do not persist the selection.
- [x] Create a calm bright-theme hero with `PageHeader`, an asset-allocation icon, a “静态教育示例” badge, and the permanent disclaimer directly under the heading.
- [x] Render four selectable asset-band cards with an accessible button pattern (`aria-pressed`), displaying only the asset range and one-sentence conservative framing. The selected state should be clear through the established accent/border treatment rather than relying on color alone.
- [x] Make the central content a two-column desktop layout that collapses to one column on narrow screens:
  - left: “配置概览” with the illustrative total, a CSS `conic-gradient` allocation ring (or a horizontal stacked bar if gradient contrast is insufficient), and a labelled legend with percentage and illustrative amount;
  - right: “保守配置的前提” with three concise guardrails: emergency liquidity, debt/insurance priority, and no-leverage/diversification discipline.
- [x] Add a “资金分桶示例” section where each of the four categories has an icon, label, percentage, example amount, and neutral explanatory copy. Amounts must visibly be labelled “示例金额”.
- [x] Finish with a subdued “使用边界” panel covering the non-personalised nature of the page, non-guaranteed outcomes, and the need to evaluate individual circumstances. Do not add a CTA that opens an order, portfolio write, AI analysis, or external financial-product page.
- [x] Reuse the existing light visual language (`GlassCard`, muted slate text, restrained cyan/emerald accents, rounded panels). Do not introduce a chart dependency or global theme override.

### Task 3: Expose the page without coupling it to user data

**Files:**
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/components/layout/Layout.tsx`

- [x] Lazy-load `AssetAllocation` in the router and add a stable `/asset-allocation` route inside the normal application layout.
- [x] Do not wrap this route in a private-resource guard, because it consumes no user data and must make no assumption about a login/session.
- [x] Add a single “资产配置” entry to the sidebar/top navigation, using an existing lucide icon such as `Landmark` or `Scale` and destination `/asset-allocation`.
- [x] Preserve all existing routes, labels, ordering, active-route logic, and responsive behavior. This work must not change the existing `/watch`, `/settings`, `/daily-review`, or sector-data paths.

### Task 4: Run regression and visual checks

**Files:**
- Verify: `frontend/tests/asset-allocation-contract.test.mjs`
- Verify: `frontend/src/pages/AssetAllocation.tsx`

- [x] Run the focused static contract test:

```powershell
node --test tests\asset-allocation-contract.test.mjs
```

- [x] Run the existing frontend route/private-assets contracts, ensuring this page did not loosen private-route controls:

```powershell
node --test tests\auth-route-contract.test.mjs tests\private-assets-contract.test.mjs tests\asset-allocation-contract.test.mjs
```

- [x] Run the production frontend build:

```powershell
npm run build
```

- [x] Manually inspect `http://127.0.0.1:5900/asset-allocation` in the running local app at desktop and mobile widths. Confirm all four choices switch content, the amounts/percentages correspond to the static-data table, labels identify the figures as examples, no request is made when switching tiers, and the disclaimer remains visible.

## Acceptance criteria

- `/asset-allocation` is visible in navigation and loads without a login, API call, database query, or AI call.
- Four asset bands are selectable; every selected scenario displays percentages totaling 100% and matching example amounts.
- The visual hierarchy is polished in the current bright theme and usable on narrow screens.
- The page never represents static figures as market data or a personalised recommendation.
- Existing route/auth/private-assets contract tests and the frontend production build pass.

## Compatibility, security, and rollback

- There is no database migration, API contract change, external data-provider call, credential use, or model-cost impact.
- This is additive: existing pages and user data remain unchanged.
- Rollback is a safe code-only removal of the route, navigation item, page, static data file, and its focused test. No persisted state requires cleanup.

## Out of scope

- User-entered amounts, personalised risk profiling, saved allocations, portfolio imports, rebalancing, trade execution, backtesting, product selection, and AI-generated advice.
- Live asset prices, yield curves, macro views, real-time allocation optimization, or any linkage to the existing sector/stock data system.
