# notebooks/ — Jupyter Notebook

本目录存放研究用 Jupyter Notebook。

## 当前阶段约束

项目处于 **Environment Setup 阶段**，因此当前：

- **不创建任何策略 Notebook**
- 本目录只保留本说明文件

## 后续用途（待用户明确指令后）

- 数据探索与可视化
- 因子分布检查
- 回测结果分析

## 启动方式

容器内：

```bash
jupyter notebook --ip=0.0.0.0 --port=8888 --allow-root --no-browser
```

或使用 Dev Container：打开 `.ipynb` 文件后选择容器内 Python 内核。

## 注意

- Notebook 执行产物（`.ipynb_checkpoints/`）已被 `.gitignore` 忽略
- 不要把包含真实账号、Token、行情数据的输出提交到 Git
