#!/bin/bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple -q
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn -q
pip config set global.retries 10 -q

pip install -q --no-cache-dir hikyuu==2.6.8.4 2>/dev/null

echo "=== 方案1: LD_PRELOAD 预加载 libstdc++ ==="
LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6 python <<'PYEOF'
try:
    import hikyuu
    print("OK with LD_PRELOAD, version =", getattr(hikyuu, "__version__", "(no attr)"))
except Exception as e:
    print("FAILED:", type(e).__name__, str(e)[:200])
PYEOF

echo
echo "=== 方案2: 加大 glibc 静态 TLS 预留（需重新 exec，此处仅测 LD_PRELOAD 是否够）==="
echo "跳过（容器内无法改 glibc 参数）"
