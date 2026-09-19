#!/bin/bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple -q
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn -q
pip config set global.retries 10 -q

echo "=== 安装 hikyuu ==="
pip install -q --no-cache-dir hikyuu==2.6.8.4 2>&1 | tail -3
echo "install exit: $?"
echo

echo "=== 导入测试 ==="
python <<'PYEOF'
import hikyuu
print("hikyuu import OK, version =", getattr(hikyuu, "__version__", "(no attr)"))
PYEOF
echo "import exit: $?"
