# 依赖冲突记录：Hikyuu 与 RQAlpha

> Environment Setup 阶段实测记录。所有结论均经 pip 解析器验证，非推测。

## 问题

任务要求在同一 Docker 容器内同时安装 `hikyuu` 与 `rqalpha`。
首次尝试安装两者最新版时，pip 解析失败。

## 实测证据

### 命令

```bash
pip install --dry-run "hikyuu==2.8.2" "rqalpha==6.4.0"
```

### pip 输出（原文）

```
ERROR: Cannot install hikyuu==2.8.2 and rqalpha==6.4.0 because these
package versions have conflicting dependencies.

The conflict is caused by:
    hikyuu 2.8.2 depends on numpy>=2.0
    rqalpha 6.4.0 depends on numpy<2.0.0; python_version <= "3.11"
```

结论：`ResolutionImpossible`。

## 冲突根因

| 包 | 版本 | numpy 要求 | pandas 要求 |
|----|------|-----------|------------|
| hikyuu | 2.8.2 | `numpy>=2.0` | `pandas>=2.3.0` |
| rqalpha | 6.4.0 | `numpy<2.0.0` (py<=3.11) | `pandas>=1.0.5, <3.0.0` |

**numpy 要求完全对立**：一个要 >=2.0，一个要 <2.0，无交集。

rqalpha 的 `numpy<2.0.0` 是带环境标记的（`python_version <= "3.11"`），
因为 numpy 2.x 的 ABI 变更会破坏 rqalpha 依赖的 C 扩展（rqrisk / h5py 等）。
本环境为 Python 3.11，因此该限制生效。

## 解决方式

按 AGENTS.md 原则（不暴力升级或降级，查找兼容版本），
定位 hikyuu 最后一个**不强制** `numpy>=2.0` 的版本。

### 各版本 numpy 要求实测

| hikyuu 版本 | numpy 要求 | pandas 要求 | 可否与 rqalpha 共存 |
|-------------|-----------|------------|-------------------|
| 2.8.2 | `numpy>=2.0` | `pandas>=2.3.0` | 否 |
| 2.7.9 | `numpy>=2.0` | `pandas>=2.3.0` | 否 |
| 2.7.6 | `numpy>=2.0` | `pandas>=2.3.0` | 否 |
| **2.6.8.4** | **无版本限制** | `pandas>=1.0.4` | **是** |

数据来源：各版本 wheel 内 `METADATA` 的 `Requires-Dist` 字段，逐一解包核对。

### 结论

锁定 **hikyuu==2.6.8.4** + **rqalpha==6.4.0**，numpy 固定为 **1.x** 系列。

## 代价与影响

- hikyuu 2.6.8.4 与最新版（2.8.x）存在版本差，新特性不可用
- 但这是当前唯一能让两个框架共存的组合，且不影响环境搭建目标
- 若将来需要 hikyuu 2.8.x，则必须放弃 rqalpha 或为其单开容器

## 未采取的做法（及原因）

| 做法 | 未采用原因 |
|------|-----------|
| 强制升级 numpy 到 2.x | 会破坏 rqalpha 的 C 扩展，属"暴力升级" |
| 强制降级 rqalpha | 属"暴力降级"，且旧版未必兼容 |
| 装 numpy 2.x 后用兼容层 | 引入不确定因素，非必要条件 |
| 拆成两个容器 | 任务明确要求同一服务 `quant-research` 内共存 |

## 复现方式

```bash
docker compose build
docker compose run --rm quant-research python -c "import hikyuu, rqalpha; print('ok')"
```
