# 依赖冲突记录：Hikyuu 与 RQAlpha

> Environment Setup 阶段实测记录。所有结论均经容器内实测验证，非推测。
> 最后更新：2026-09-19

## 结论速览

| 项目 | 最终值 |
|------|--------|
| Python | 3.12.11 |
| 基础镜像 | mambaorg/micromamba:1.5.10-noble（Ubuntu 24.04） |
| hikyuu | 2.8.2 |
| rqalpha | 6.4.0 |
| numpy | 2.3.5 |
| 镜像标签 | quant-research:py3.12 |

验证结果：`tests/test_environment.py` 14 passed，9 个核心模块 import 全部通过。

---

## 第一层问题：numpy 版本对立（表象）

任务要求在同一容器内同时安装 `hikyuu` 与 `rqalpha`。

### 实测证据

```bash
pip install --dry-run "hikyuu==2.8.2" "rqalpha==6.4.0"
```

```
ERROR: Cannot install hikyuu==2.8.2 and rqalpha==6.4.0 because these
package versions have conflicting dependencies.

The conflict is caused by:
    hikyuu 2.8.2 depends on numpy>=2.0
    rqalpha 6.4.0 depends on numpy<2.0.0; python_version <= "3.11"
```

### 冲突结构

| 包 | numpy 要求 | 生效条件 |
|----|-----------|---------|
| hikyuu 2.7+ | `numpy>=2.0` | 无条件 |
| rqalpha 6.4.0 | `numpy<2.0.0` | `python_version <= "3.11"` |
| rqalpha 6.4.0 | `numpy>=2.0.0` | `python_version >= "3.12"` |

关键点：rqalpha 的约束**带环境标记**。Python 版本决定了它要哪一边。

### 最初（错误）的解法

按照"不暴力升降级、找兼容版本"的原则，最初锁定 hikyuu==2.6.8.4
——这是最后一个不强制 `numpy>=2.0` 的版本，与 Python 3.11 下的 rqalpha 共存。

该方案在依赖层面成立，但运行层面崩溃。见下一节。

---

## 第二层问题：hikyuu 2.6.8.4 的 C 扩展崩溃（真因）

### 现象

按 2.6.8.4 方案构建镜像成功后，import 报错层层变化：

1. `python:3.11.9-slim-bookworm` 基础镜像：
   `ImportError: /lib/x86_64-linux-gnu/libstdc++.so.6: version 'GLIBCXX_3.4.32' not found`
2. Debian 13 trixie / micromamba(conda)：
   `ImportError: ... cannot allocate memory in static TLS block`
3. 去掉 conda 的 libstdc++ 后改用系统库：仍是 TLS 报错

### 定位过程

用 `ctypes.CDLL` 绕过 hikyuu 的异常包装，直接加载 C 扩展：

```python
import ctypes
ctypes.CDLL("/opt/conda/lib/python3.11/site-packages/hikyuu/cpp/core311.so",
            mode=ctypes.RTLD_GLOBAL)
```

结果：**进程直接 SIGILL 崩溃（exit 132），连异常都抛不出来**。

同一个容器、同一个环境，换成 hikyuu 2.8.2 的 core311.so：

```
Initialize hikyuu_2.8.2_202608201740_RELEASE_linux_x64 ...
core311 LOAD OK
```

### 根因

hikyuu 2.6.8.4 的预编译 C 扩展在本机 CPU 上触发**非法指令（SIGILL）**。

本机 CPU：Intel Core Ultra 9 185H（支持 AVX/AVX2，并非老 CPU）。

官方文档佐证（hikyuu.readthedocs.io/zh-cn/latest/install.html）：

> 2.6.8/2.6.9 版本，部分 x86 cpu 不支持 avx 指令集的老旧机器, 会崩溃。
> 建议升级到 2.7.0 以上版本。

之前所有的 GLIBCXX 缺失、TLS 分配失败报错，都是这个崩溃在不同
包装层/不同基础镜像下的表面症状，不是各自独立的问题。

### 正确解法

升级 hikyuu 到 2.7+，同时升级 Python 到 3.12 以消除 numpy 对立：

- Python 3.12 → rqalpha 要求 `numpy>=2.0`
- hikyuu 2.8.2 → 要求 `numpy>=2.0`
- 两者一致，冲突消失

实测（Python 3.12.11 环境）：

```
Would install ... hikyuu-2.8.2 ... numpy-2.3.5 ... rqalpha-6.4.0 ...
```

`DONE_EXIT=0`，解析通过。

---

## 第三层问题：基础镜像选型

官方文档明确 pip 安装的支持范围：

> 支持的操作系统：64位 Windows7(x86 cpu)及以上版本、Ubuntu、MacOSX(arm)，
> 其他建议使用源码编译安装
> Windows(x86 cpu), Ubuntu24.04及以上、mac(arm cpu)支持 pip 安装

Debian 不在支持列表内（故 bookworm/trixie 出现问题有其必然性）。

最终采用 `mambaorg/micromamba:1.5.10-noble`——Ubuntu 24.04 底座，
符合官方支持范围。系统自带 libstdc++ 6.0.33 含 GLIBCXX_3.4.32/3.4.33，
符号充足。

不需要额外安装 conda 的 `libstdcxx-ng`/`libgcc-ng`
（conda 的 libstdc++ 有 RPATH 优先问题，反而添乱；系统库已足够）。

---

## 最终 requirements.txt 关键版本

| 包 | 版本 |
|----|------|
| hikyuu | 2.8.2 |
| rqalpha | 6.4.0 |
| numpy | 2.3.5 |
| pandas | 2.3.3 |
| scipy | 1.16.3 |
| matplotlib | 3.10.9 |
| akshare | 1.18.88 |
| pytest | 8.4.2 |

---

## 未采取的做法（及原因）

| 做法 | 未采用原因 |
|------|-----------|
| 保留 hikyuu 2.6.8.4 | C 扩展 SIGILL 崩溃，无法修复 |
| 强制降级 numpy 到 1.x | 会与 hikyuu 2.7+ 冲突，且需保留崩溃版本 |
| 用 LD_PRELOAD 注入 libstdc++ | 实测导致 SIGILL（exit 132），不可行 |
| 换回 Debian 基础镜像 | 非官方支持平台 |
| 源码编译 hikyuu | 备选方案；升级版本后已不必要 |
| 拆成两个容器 | 任务明确要求同一服务 `quant-research` 内共存 |

---

## 复现方式

```bash
docker compose build
docker compose run --rm quant-research pytest tests -v
docker compose run --rm quant-research python -c "import hikyuu, rqalpha; print('ok')"
```
