# quant-research 研究环境
# 固定 Python 版本，不使用 latest
FROM python:3.11.9-slim-bookworm

# 基础构建依赖（hikyuu 需要编译工具链；rqalpha 需要部分系统库）
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        g++ \
        gfortran \
        libboost-all-dev \
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

# 清华源加速（可选，保留官方源作为回退）
# RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /workspace

# 先装依赖，利用 Docker 层缓存
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# 不复制 data、logs、.env、secrets（由 compose 挂载）
# 不运行任何策略，仅保留环境

CMD ["bash"]
