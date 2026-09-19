# AGENTS.md — 项目强制约束

本文件对本仓库内的所有自动化助手（Codex / Claude Code 等）具有强制效力。
每次在仓库内工作前必须先读本文件。

## 阶段

1. 当前项目处于 **Environment Setup 阶段**。

## 禁止事项（硬约束）

2. 未经用户明确指令，**禁止创建交易策略**。
3. **禁止运行回测**。
4. **禁止模拟交易**。
5. **禁止真实交易**。
6. **禁止接入真实券商**。
7. **禁止读取或保存真实金融账户凭证**。
8. **禁止提交**下列内容到 Git：

```
.env
data/
logs/
secrets/
Token
密码
Cookie
账号
```

## 技术栈定位

9. Hikyuu 未来作为**主研究框架**。
10. RQAlpha 未来作为**独立验证框架**。
11. JoinQuant 未来作为**模拟环境**。

## 版本控制

12. GitHub 当前不可用（账号 suspended）。
13. 当前**只允许本地 Git 版本控制**。
14. 未经用户明确指令，**不配置任何远程 Git 仓库**。

## 环境约束

15. 所有 Python 量化依赖只装在 Docker 容器内，
    **不在 Windows 宿主机全局 Python 环境安装**。
16. **不使用 .venv** —— 宿主机不建虚拟环境。
17. 容器内不复制 `data` / `logs` / `.env` / `secrets`，由 compose 挂载。
18. 不部署 PostgreSQL / MySQL / MongoDB / Redis 等数据库。

## 允许的操作

19. 只允许建立**环境测试**：`tests/test_environment.py`，
    仅确认 `numpy` / `pandas` / `akshare` / `hikyuu` / `rqalpha` 能否正常加载。

不得：
- 获取真实行情做策略
- 创建交易信号
- 执行回测
- 创建模拟交易

20. 允许 `pip install` 容器内依赖、`pytest`、启动 Jupyter，
    但不得创建策略 Notebook（`notebooks/` 当前只放 README）。

## 当前不安装的框架

```
Qlib  vn.py  WonderTrader  Freqtrade  Backtrader
QUANTAXIS  ZVT  QMT  MiniQMT  PTrade  easytrader  EasyXT
```

## 依赖冲突处理原则

若 Hikyuu 与 RQAlpha 发生依赖冲突：

- **不暴力升级或降级**
- 查找兼容版本
- 固定 `requirements.txt`
- 记录问题和解决方式（写入 `docs/`）
