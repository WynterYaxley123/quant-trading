#!/bin/bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple -q
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn -q
pip config set global.retries 10 -q

pip install -q --no-cache-dir hikyuu==2.6.8.4 2>/dev/null
echo "install rc=$?"
echo

echo "### A. 无 LD_PRELOAD"
python /p/_imp.py
echo
echo "### B. LD_PRELOAD libstdc++"
LD_PRELOAD=/lib/x86_64-linux-gnu/libstdc++.so.6 python /p/_imp.py
echo
echo "### C. LD_PRELOAD libstdc++ + libgcc_s"
LD_PRELOAD="/lib/x86_64-linux-gnu/libstdc++.so.6:/lib/x86_64-linux-gnu/libgcc_s.so.1" python /p/_imp.py
