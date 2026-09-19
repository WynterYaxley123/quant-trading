"""框架适配器。

当前：
- ``hikyuu`` —— Hikyuu 2.8.2 适配器（KData ↔ canonical frame，
  ranking → Portfolio/Selector/AllocateFunds 结构）。

未来可在此新增 ``rqalpha`` 适配器，复用同一套纯策略核心
（``src.factors`` / ``src.strategies`` / ``src.risk``）。
纯核心不依赖任何框架，这是刻意设计。
"""
