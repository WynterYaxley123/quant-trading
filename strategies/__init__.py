"""策略包集合。

每个子目录是一个**自包含**的策略包，包含自己的代码、配置、测试与文档。

调用方式::

    from strategies.sw_sector_rotation import SWSectorRotationCore

当前策略：

- ``sw_sector_rotation`` —— SW Sector Rotation Core
  （Legacy china-market-data v5 迁移，状态 MIGRATED / NOT YET BACKTESTED）

设计约定：

- 策略包之间互相独立，一个策略的改动不影响另一个。
- 策略包与顶层 ``src/``（框架）保持分离。
- 复用需求出现**之前**不做共享抽象，避免提前增加间接层。
"""
