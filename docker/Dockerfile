# quant-research 研究环境
# 基础镜像：micromamba（Ubuntu 24.04 noble 底座）
#
# 选型经过（2026-09-19）：
#   起初用 python:3.11.9-slim-bookworm，hikyuu 2.6.8.4 报 GLIBCXX_3.4.32 缺失
#   换 trixie / conda 后转为 TLS 报错，最终定位真因：
#     hikyuu 2.6.8.4 的预编译扩展 core311.so 在本机 CPU 上 SIGILL 崩溃
#     （官方承认 2.6.8/2.6.9 有崩溃问题，建议升 2.7.0+）
#   故升级 hikyuu 至 2.8.2，并升 Python 至 3.12 以消除与 rqalpha 的 numpy 冲突
#   本镜像选 noble 是因为官方 pip 安装仅支持 Ubuntu 24.04+ / Windows / macOS
#   详见 docs/dependency_conflicts.md
FROM mambaorg/micromamba:1.5.10-noble

USER root

# apt 重试配置（本网络下镜像源存在间歇性 502，靠重试自动恢复）
RUN printf 'Acquire::Retries "8";\nAcquire::http::Timeout "30";\nAcquire::https::Timeout "30";\n' \
    > /etc/apt/apt.conf.d/99retries

# 基础构建依赖（rqalpha / akshare 需要的系统库；conda 提供 C++ 运行库）
RUN apt-get update \
    && apt-get install -y --no-install-recommends --fix-missing \
        build-essential \
        g++ \
        gfortran \
        libopenblas-dev \
        liblapack-dev \
        libhdf5-dev \
        libssl-dev \
        libffi-dev \
        git \
        curl \
        ca-certificates \
        tzdata \
    && ln -snf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

USER $MAMBA_USER

WORKDIR /workspace

# 固定 Python 版本（conda 包里显式指定 3.12；版本决策见 requirements.txt）
ARG PY_VERSION=3.12.11
RUN micromamba install -y -n base -c conda-forge \
        python=${PY_VERSION} \
        pip \
        setuptools \
        wheel \
    && micromamba clean --all --yes

# conda base 环境的 bin 路径（切到非 root 用户后需显式指定）
ENV CONDA_BIN=/opt/conda/bin
ENV PATH=${CONDA_BIN}:${PATH}

# 确认 Python 与 pip 就位（构建期自检，失败即中断）
RUN python --version && pip --version

# pip 重试与超时（hikyuu wheel 约 73MB，网络抖动需重试）
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    && pip config set global.timeout 60 \
    && pip config set global.retries 10

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# 不复制 data、logs、.env、secrets（由 compose 挂载）
# 不运行任何策略，仅保留环境

CMD ["bash"]
