# Third-Party Notices — Shenwan Research Dashboard

本项目遵守所有依赖与参考项目的许可证。本文件记录：

1. 被**直接复制/改写**的上游代码来源与许可证；
2. 通过 npm 引用的**依赖包**及其许可证（不复制其源码）。

本仓库自有代码和文档按根目录 [MIT License](../LICENSE) 授权；以下第三方内容保留各自许可证与版权声明。软件许可不授予市场数据再分发权。

---

## A. 直接改编（adapted）的上游代码

### shadcn/ui（via satnaing/shadcn-admin 模式参考）

- **project**: shadcn-ui/shadcn/ui 组件模式；结构研究对象为 satnaing/shadcn-admin
- **license**: MIT License
- **copyright and permission notice**: [完整上游 MIT 声明](licenses/shadcn-ui-MIT.txt)，仅适用于上游改编部分，不为本项目自有代码授予许可。
- **what was adapted**: `src/components/ui/` 下的组件写法约定（CVA 变体 + `cn()` 类名合并 + Radix primitive 封装）：Button、Card、Badge、Dialog、Tooltip、Collapsible、Separator、Skeleton、Table 样式与 CSS 变量主题令牌（shadcn 设计令牌体系）。App shell 布局思路（sidebar + header + content）参考其架构后重写。
- **not copied**: 其 demo 业务页面、demo 数据、RTL 魔改组件、品牌/logo、Clerk 认证代码、任何图片素材。

### Tremor（patterns only）

- **project**: tremorlabs/tremor（Tremor Raw）
- **license**: Apache License 2.0
- **what was adapted**: 仅 UI **pattern**（metric card 信息层级、dashboard 卡片网格组合、图表 card 结构、数值格式化约定、克制分类色板）。未复制任何源码文件。
- **not copied**: 任何组件源码、品牌、demo 资产。

### Apache Superset（UX only）

- **project**: apache/superset
- **license**: Apache License 2.0
- **what was adapted**: 仅信息架构思想（dashboard 分层、filter 置顶、explore 与 presentation 分离、行下钻 detail 面板）。未复制任何源码、样式或素材。

以下项目未复制、未改编任何内容，仅作架构研究记录（见 [reference review](docs/reference-review.md)）：

- TanStack/table（MIT License）— 以 npm 依赖形式使用
- perspective-dev/perspective（Apache License 2.0）— 未使用、未复制

---

## B. npm 运行时依赖（引用，不复制源码）

| Package | License | 用途 |
|---------|---------|------|
| react / react-dom | MIT | UI 框架 |
| @tanstack/react-router | MIT | 路由与 URL 状态 |
| @tanstack/react-table | MIT | headless 表格 |
| recharts | MIT | 图表引擎（Tremor 同源引擎） |
| zod | MIT | API 响应运行时校验 |
| clsx / tailwind-merge | MIT | 类名工具 |
| class-variance-authority 0.7.1 | Apache-2.0 | 组件变体工具 |
| lucide-react | ISC | 图标 |
| @radix-ui/react-slot | MIT | 组件组合原语 |
| @radix-ui/react-dialog | MIT | 可访问 dialog（sector 明细面板） |
| @radix-ui/react-tooltip | MIT | 可访问 tooltip（单位/术语说明） |
| @radix-ui/react-collapsible | MIT | 可访问折叠区（diagnostics 明细） |

开发依赖（TypeScript、Vite、Tailwind CSS、Vitest、Testing Library、ESLint 等）均为 MIT/Apache-2.0/BSD 许可的工具链，仅用于构建与测试，不进入发布产物。

完整许可证文本随各 npm 包分发于 `node_modules/<pkg>/LICENSE`。

---

## C. 品牌与素材声明

- 本项目**不包含**任何上游项目的 logo、品牌标识或受版权保护的 demo 素材。
- 产品名称「Shenwan Research Dashboard / Sector Index Research」及其导航、内容、研究语义均为本项目自有。
- Mock 模式数据为**合成测试数据**（synthetic），不来自任何真实研究结果，也不来自任何第三方数据源。
