"""因子库（框架无关）。

- :mod:`src.factors.sector_rotation` —— MA/MAPP 因子族、波动率、反转、回撤、RSI
- :mod:`src.factors.rsrs` —— RSRS 阻力支撑相对强度
- :mod:`src.factors.macro_pit` —— 宏观因子 Point-In-Time 时点对齐（默认关闭）

全部纯函数：输入 canonical OHLCVA DataFrame，输出因子 DataFrame，无 I/O。
"""
