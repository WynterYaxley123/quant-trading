# 飞书集成规划

> 状态：**规划 + 接口骨架。当前不发真实通知、不填真实凭证。**
> 最后更新：2026-09-19

---

## 1. 飞书角色

飞书未来负责：

- 结果展示
- 通知
- 异常通知
- 任务入口
- 审批

**飞书不是代码开发环境。**

---

## 2. 统一消息格式

```
【Quant Research Completed】

Strategy:
Version:
Status:

Hikyuu:
  Annual Return:
  Max Drawdown:
  Sharpe:

RQAlpha:
  Annual Return:
  Max Drawdown:
  Sharpe:

Validation:  PASS / FAIL
Report:
Git Commit:
```

### 异常通知格式

```
【Quant Task Failed】

Task:
Strategy:
Stage:       (哪个环节失败)
Error:
Time:
Log:
```

---

## 3. 配置项

以下为预留配置，**真实值只允许放 `.env`**：

```bash
FEISHU_WEBHOOK=
FEISHU_APP_ID=
FEISHU_APP_SECRET=
```

`.env` 已在 `.gitignore` 中，**不得进入 Git**。
`.env.example` 中对应项保持为空值。

---

## 4. 接口骨架

骨架代码位于 `src/notifications/feishu.py`。

设计原则：

1. **dry-run 优先**：默认不发送真实请求，只打印将要发送的内容
2. 未配置凭证时，函数返回"未配置"状态而非抛异常
3. 凭证缺失不阻塞主流程
4. 发送失败记录日志，不中断回测/验证任务

```python
# 使用示意（当前阶段不实际调用）
from src.notifications.feishu import send_report

result = send_report(payload, dry_run=True)
```

---

## 5. 目录与文件

| 路径 | 用途 |
|------|------|
| `src/notifications/feishu.py` | 通知接口骨架 |
| `src/notifications/templates.py` | 消息模板 |
| `docs/feishu_integration.md` | 本文件 |

---

## 6. 未来流程

```
回测/验证完成
      ↓
生成报告（reports/）
      ↓
构造消息 payload
      ↓
飞书推送（webhook 或应用消息）
      ↓
用户查看 / 审批
```

---

## 7. 当前禁止事项

- 填写真实凭证
- 发送真实通知
- 配置飞书应用
- 接入审批流

**当前只建立骨架与配置模板。**
