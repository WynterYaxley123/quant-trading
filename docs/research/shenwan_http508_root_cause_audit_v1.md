# SHENWAN Official HTTP 508 Root-Cause Audit V1

- FINAL STATUS: SHENWAN_PUBLIC_CLIENT_CONTRACT_CHANGED
- ROOT CAUSE: Tengine 边缘网关按 User-Agent 拒绝非浏览器客户端——curl / python-requests
  的默认 UA 取回空 body 的 HTTP 508（catalog、trend、连主页都一样），换成公开前端浏览器
  自身的 UA 后同一 URL、同一 TLS、同一网络立刻 200。单变量切换即 508↔200，根因确凿。
- CONFIDENCE: HIGH（UA 单变量对照、WSL/Windows/Docker 三环境一致复现、508 与 200 响应均已落盘取证）
- HEAD: b8c1e2ced79b6fd89c5fe3a6cdee04253973ba54（branch experiment/sw-sector-index-research-baseline）

## 网络与 TLS

- TLS status: PROJECT_LOCAL_STRICT_CHAIN_COMPLETION PASS（服务端仅发 leaf；项目本地补
  GeoTrust intermediate（sha256 2182efcb…e9176c1）后严格验证 OK；全程未用 verify=False）
- catalog status: 508（修复前）→ 200（UA 修复后，probe=PASS）
- trend status: 508（修复前）→ 200（UA 修复后，probe=PASS）
- 508 fingerprint: HTTP/2 508、server: Tengine、content-length: 0、body 空
  （sha256 e3b0c442…852b855）、无 Set-Cookie/Location/X-Cache/X-Request-ID；
  catalog 与 trend 完全同构 → COMMON_GATEWAY_FAILURE=true
- homepage status: 浏览器 UA 302 正常跳转；curl UA 508（整站同一 UA 闸门）

## 前端请求语义

- frontend API endpoint: 未迁移——就是历史 endpoint
  https://www.swsresearch.com/institute-sw/api/index_publish/{current,trend}/
- frontend method: GET
- minimal request contract: GET + 浏览器形态 User-Agent + 严格 TLS（项目 bundle）。
  Accept / Referer / Origin 均非必需；query 参数与 updater 现有 check_url 契约完全一致
  （page/page_size=50/indextype=二级行业；swindexcode/period=DAY，中文参数 percent-encode）
- anonymous session required? NO（无 cookie 的裸请求即 200）
- login/captcha/challenge? NO（全程无任何访问控制挑战）
- endpoint migrated? NO
- schema compatible? YES（catalog：code/message/data + count/results/next，count=124、
  50/页分页；trend：10 字段 BAR_FIELDS 与历史 raw 完全一致，6463 行，1999-12-30→2026-09-24）
- representative 200 obtained? YES（catalog 8232B sha256 1dd884db…、trend(801012) 1500526B
  sha256 8df59bb5…）
- overlap result: 801012 历史 6459 行 vs 新响应 6459 公共行 → 0 mismatch（0 revision），
  新增 4 行为 append-only 正常增量

## 环境对照

- Docker vs host difference: 无（WSL/Windows host/Docker 容器三处行为完全一致；
  容器内仅需走既有 prepare_tls 补链机制）
- proxy finding: Windows 用户级 HTTP(S)_PROXY=http://127.0.0.1:10808 存在，但不影响本链路
  （三环境 UA 敏感行为一致；WSL 无代理变量）
- HTTP version finding: HTTP/2 与 HTTP/1.1 均 200，与 508 无关

## 变更与运行记录

- updater patch? YES——src/data/providers/shenwan_official_update.py 的 OfficialClient
  仅新增浏览器形态 User-Agent（含注释）；未动 endpoint/schema/TLS/数据路径/研究逻辑
- dry-run? BLOCKED_BY_DESIGN——cycle 要求 clean worktree，patch 与本报告未 commit，
  被 SHENWAN_UPDATER_DIRTY_WORKTREE_BLOCKER 正确拦截。核心等价验证已覆盖：
  probe SOURCE_HEALTH_PASS + 代表 sector overlap 0 mismatch。commit 后可跑 cycle --dry-run
- historical revision count: 0（代表 sector overlap 实测）
- canonical modified? FALSE
- snapshot modified? FALSE
- Validation opened? FALSE
- Validation performance read? FALSE
- Final OOS read? FALSE

## 证据与报告

- report path: docs/research/shenwan_http508_root_cause_audit_v1.md
- evidence path: D:\QuantForge\temp\shenwan-http508-audit-v1\（508/200 的 header+body、
  严格 bundle、最小请求矩阵、overlap 统计，见其 README.md）

## 结论

这不是封锁、不是 WAF、不是接口迁移，而是公开前端本就用浏览器 UA 请求、边缘网关对
非浏览器 UA 给 508。updater 以公开访问语义（浏览器 UA）恢复可用；无账号、无 cookie、
无挑战绕过。

NO CANONICAL MARKET DATA WAS MODIFIED
NO NEW SHENWAN SNAPSHOT WAS PUBLISHED
VALIDATION PERFORMANCE WAS NOT READ
VALIDATION REMAINS SEALED AND UNSEEN
FINAL OOS REMAINS SEALED
NO LOGIN, CAPTCHA, WAF, OR ACCESS-CONTROL BYPASS WAS PERFORMED
VERIFY_FALSE WAS NOT USED

NEXT SAFE ACTION: REVIEW & COMMIT UPDATER UA PATCH, THEN RUN cycle --dry-run
(124/124 FETCH + OVERLAP + REVISION COUNT), THEN F1 VALIDATION READINESS CONTINUATION.
