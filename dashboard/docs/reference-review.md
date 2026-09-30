# Reference Review — Shenwan Research Dashboard V1

本文件记录 Dashboard 开工前对 5 个成熟开源项目的实际研究结论。
目标：**轻度魔改成熟结构，替换全部 demo domain**，而不是从零设计或整仓复制。

每个项目包含：project、license、patterns worth adopting、patterns NOT suitable、exact decisions for our dashboard。

---

## 1. satnaing/shadcn-admin（Primary UI Code Reference）

- **project**: shadcn-admin —— 基于 shadcn/ui 的管理后台 UI 架构（v2.2.1，14k+ stars）
- **license**: MIT
- **研究对象**: app shell、sidebar、navigation、responsive layout、dark/light mode、command/search、route organization、page spacing、cards、tables、empty states、mobile behavior

### Patterns worth adopting

1. **App shell 架构**：固定 sidebar（desktop）+ 顶栏（mobile menu 触发 drawer）+ 内容区 `Outlet`。层级为 layout → page → section → card，页面间距用统一 spacing scale。
2. **技术栈组合（其 package.json 实证）**：Vite + React 19 + TypeScript + **TanStack Router**（config/file 路由）+ **TanStack Table** + Tailwind CSS v4（`@tailwindcss/vite`）+ Radix UI primitives + `class-variance-authority`/`clsx`/`tailwind-merge` + lucide-react 图标 + **recharts** 图表 + zod 校验。
3. **shadcn/ui 组件模式**：CVA 变体 + `cn()` 合并类名 + Radix 无头原语包一层可访问组件（button/card/dialog/select/tooltip/tabs/collapsible/separator/skeleton）。组件源码放在自己仓库内可改（shadcn 模式），不绑死上游版本。
4. **Light/dark mode**：`class` 策略 + CSS variables 设计令牌，两种模式都完整调校。
5. **Responsive**：sidebar 在移动端转 drawer；卡片 grid 自适应 reflow；表格局部横向滚动。
6. **Empty / loading 状态**：页面级 skeleton 与 empty state 组件是该模板的固定实践。

### Patterns NOT suitable

1. **Clerk 认证**（auth/partial）—— 本 Dashboard 无账户体系，第一版运行在本机，不伪装 security system。
2. **Demo business domain**（users / tasks / products / orders 等 10+ 业务页）—— 全部不保留，替换为 research domain 页面。
3. **RTL 支持**与其带来的组件魔改维护成本 —— 无此需求。
4. **zustand / TanStack Query / axios / react-hook-form** —— 其 demo 用它们做客户端状态、表单与 HTTP；本项目 explorer 状态全部进 URL（§38），无表单，HTTP 需求仅一个 read-only fetch client（§37 自带 AbortController/timeout/typed errors），引入它们属于过度设计。
5. **cmdk 全局命令面板** —— V1 导航仅 6 项，侧边栏直达；命令搜索列入未来扩展，不为它引依赖。
6. **react-top-loading-bar / sonner / input-otp / react-day-picker** 等 demo 周边组件 —— 无对应场景。

### Exact decisions for our dashboard

- 采用 **Vite + React 19 + TypeScript + TanStack Router + TanStack Table + Tailwind v4 + Radix + CVA** 的组合，与该 reference 当前稳定结构保持一致。
- 采用其 app shell 布局骨架（sidebar + header + content），但**重写全部导航与内容**为 research 语义（Overview / Research / Diagnostics / Research Integrity）。
- shadcn 组件**手工移植最小子集**（button、card、badge、table、dialog、tooltip、collapsible、separator、skeleton、select=原生增强），不整包复制其 `src/components/ui`（其中含 RTL 魔改与 demo 依赖）。
- 不引入其 auth、demo 页面、demo 数据、品牌素材。

---

## 2. tremorlabs/tremor（Dashboard Component Reference）

- **project**: Tremor（现仓库为 Tremor Raw：copy-and-paste 组件库形态，35+ dashboard 组件）
- **license**: Apache-2.0
- **研究对象**: metric cards、line charts、bar charts、dashboard composition、data formatting、responsive charts、empty/loading patterns

### Patterns worth adopting

1. **Metric card 组合**：label（上）+ 大数值（中）+ 辅助说明/单位（下），卡片网格是 dashboard 的原子单元。
2. **图表组合**：图表放在带 title/描述的 card 内，同一 Y 轴单位才允许同图；分类色板克制（4-6 色、低饱和）。
3. **数据格式化约定**：数值格式化集中处理，千分位/百分比/精度统一，null 有统一占位。
4. **Responsive charts**：图表随容器宽度自适应，窄屏堆叠。
5. **empty/loading pattern**：图表容器有 loading 与 empty 两种非空白状态。

### Patterns NOT suitable

1. **整仓复制** —— 明确禁止；只取 pattern。
2. **经典 `@tremor/react` npm 包** —— 该仓库已转向 Tremor Raw「copy-paste 组件」模式（README 以 Tremor Raw 为现行形态），继续依赖其 npm 包不符合 dependency hygiene（§56「不要随意使用 abandoned packages」的风险）。
3. **其品牌与 demo 素材** —— 不复制。

### Exact decisions for our dashboard

- **图表引擎采用 recharts**（即 Tremor Raw 组件底层使用的引擎，shadcn-admin 亦采用 recharts）：满足「优先 Tremor patterns/components」且不引入第二引擎；**不引入 ECharts**。
- 自写 `components/charts/` 薄层组件（BarChartCard / TimeSeriesChart / ChartFrame），组合方式遵循 Tremor：card + title + 单位说明 + tooltip 格式化 + accessible fallback summary。
- Metric card 结构（label / value / unit hint）直接采用 Tremor 的信息层级。

---

## 3. TanStack/table（Table Reference）

- **project**: TanStack Table v8 —— headless 表格核心 + 各框架 adapter
- **license**: MIT
- **研究对象**: sorting、filtering、pagination、column visibility、server-side data pattern、responsive table handling

### Patterns worth adopting

1. **Headless 架构**：逻辑（排序/过滤/分页/列可见性）与呈现分离，UI 完全自控 —— 与 shadcn 设计体系天然契合。
2. **Sorting / column visibility / pagination**：candidate 对比表与 sector 表需要排序与列控制。
3. **Server-side data pattern**：manual 模式（manualSorting 等）—— Sector Explorer 的数据按 run/candidate/date 服务端取数（§52），表格只渲染当页 124 行。
4. **Responsive handling**：宽表局部横向滚动 + 语义化 `<th scope>`。

### Patterns NOT suitable

1. **虚拟滚动（virtualizer）** —— 当前表格 ≤ 124 行，无性能压力，不引入。
2. **grouping/aggregation/row selection** —— research 语义不需要行选择与聚合。

### Exact decisions for our dashboard

- 引入 `@tanstack/react-table` v8，写一个通用 `DataTable` 薄封装（排序 + 列可见性 + 列定义 typed）。
- Sector 表与 Candidate 表默认列序/排序固化在页面层（默认 Weighted RankIC 降序、fusedRank 升序）。
- 服务端分页字段（total/limit/offset）在 API contract 层保留，UI V1 一次取当前 date 的全部行（≤124）。

---

## 4. apache/superset（Analytics UX Reference）

- **project**: Apache Superset —— BI 平台（**仅参考 UX / information architecture**）
- **license**: Apache-2.0
- **研究对象**: dashboard hierarchy、filters、metric visualization、chart grouping、analytics layout、detail exploration、data-vs-dashboard separation

### Patterns worth adopting

1. **Dashboard hierarchy**：总览（status + 概要卡片）→ 聚合对比（charts + table）→ 单点探索（filter → chart → 明细行 → detail panel）。Overview 之于本项目 = Superset dashboard 之于其 charts。
2. **Filter 置顶**：筛选器（run / candidate / date / metric / horizon）统一放页面顶部一行，作用域清晰。
3. **Explore 与 presentation 分离**：Development/ Sector Explorer 是探索页（控件多、状态进 URL），Overview 是陈述页（只读概要）——两类页面布局刻意不同。
4. **Detail exploration**：表格行 → 侧边 detail 面板的下钻模式（Superset 的 chart → Explore 下钻的轻量等价）。
5. **Metric 语义层一致命名**：同一指标全站同名同单位（Weighted RankIC / Weighted Spread 等）。

### Patterns NOT suitable

1. **Superset backend / Python / database / SQL Lab / semantic layer 引擎** —— 明确禁止；不做 BI platform。
2. **Apache ECharts**（其可视化后端之一）—— 本项目第一版不引入。
3. **其 filter 组件复杂度**（native filter 配置体系）—— 本项目筛选项少且固定，用简单 select/search param 即可。

### Exact decisions for our dashboard

- 信息架构：`Overview（陈述）→ Candidate Comparison（对比）→ Development/Sector Explorer（探索）→ Diagnostics / Integrity（审计）`，导航顺序即认知顺序。
- 所有 explorer 筛选器写入 URL search params（refresh / back / bookmark 可恢复），对应 Superset「explore state 可保存」的体验本质。
- 行下钻用 dialog/side panel 展示 sector 明细，明确标注 Prediction ≠ realized return。

---

## 5. perspective-dev/perspective（Future Large Data Reference — evaluation only）

- **project**: Perspective —— 大数据量/流式交互分析组件（C++/WASM 查询引擎 + virtual-scrolling grid）
- **license**: Apache-2.0
- **研究对象**: large dataset explorer、virtualized grid、cross-filter（**仅未来评估，第一版不安装**）

### Patterns worth adopting（未来）

1. **Virtualized grid**：当行数进入 10 万级（如全市场股票池逐日预测）时的渲染方案。
2. **Cross-filter 交互**：图表点选联动过滤表格。
3. **流式增量更新**：若未来接入准实时研究数据。

### Patterns NOT suitable

1. **第一版安装** —— 明确禁止；当前表格 ≤ 124 行（sector 数），TanStack Table 绰绰有余。
2. **WASM 引擎 / Custom Element 体系** —— 与 React/Vite/shadcn 技术栈整合成本高，且显著增加 bundle 与构建复杂度。

### Exact decisions for our dashboard

- V1 不引入。在 `architecture.md` 记录**重新评估阈值**：单表 > 50k 行、需要跨图表 cross-filter、或需要流式更新时，再评估 Perspective（或 TanStack virtualizer 作为更轻的第一步）。

---

## 汇总决定（for our dashboard）

| 维度 | 决定 |
|------|------|
| 框架 | React 19 + TypeScript + Vite |
| 路由 | TanStack Router（explorer 状态进 URL search params） |
| 表格 | TanStack Table v8（headless 薄封装） |
| 图表 | recharts（Tremor 底层引擎）+ Tremor 组合/格式化 pattern；不用 ECharts |
| UI 体系 | shadcn/ui 模式（Tailwind v4 + Radix + CVA），手工移植最小子集 |
| 状态 | 无全局 store；URL + 本地 hook |
| 数据 | 自研 typed fetch client + adapter（real API / mock），zod 运行时校验 envelope |
| 不引入 | Clerk、cmdk、zustand、TanStack Query、axios、react-hook-form、@tremor/react、Perspective、Superset 任何组件 |
