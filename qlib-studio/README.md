# Qlib Studio - 可视化 AI 量化投资训练平台

## 项目简介

Qlib Studio 是一个基于 Web 的开源量化投资训练管理平台，提供：

- 🎨 **可视化配置**：前端表单配置所有 Qlib 参数（数据/模型/策略/回测）
- 🔄 **迭代训练**：支持多轮实验自动调度，模型版本管理
- 📊 **实时监控**：训练过程、回测指标、组合净值的实时可视化
- 📁 **实验管理**：实验记录、对比分析、模型仓库
- 🚀 **一键部署**：Docker 一键启动整个平台

## 技术栈

- **前端**：React + Ant Design + ECharts
- **后端**：FastAPI + Celery + Redis
- **数据库**：SQLite / PostgreSQL
- **ML 调度**：MLflow (Qlib 内置)
- **容器化**：Docker + Docker Compose

## 快速开始

```bash
# 克隆项目
git clone https://github.com/yourname/qlib-studio.git
cd qlib-studio

# 启动服务
docker-compose up -d

# 访问前端
open http://localhost:3000
```

## 项目结构

```
qlib-studio/
├── frontend/          # React 前端
├── backend/           # FastAPI 后端
├── docker/            # Docker 配置
├── configs/           # 默认配置模板
├── scripts/           # 辅助脚本
└── docs/              # 文档
```

## 核心功能

### 1. 数据配置
- 数据源选择（本地/远程）
- 市场选择（A股/美股）
- 时间范围配置
- 指数/标的筛选

### 2. 因子配置
- 内置 158/360 因子库
- 自定义因子表达式
- 因子预处理流水线

### 3. 模型配置
- LightGBM / XGBoost / CatBoost
- MLP / LSTM / Transformer (PyTorch)
- 超参数自动调优（Optuna）

### 4. 策略配置
- TopK Dropout
- 自定义信号策略
- 调仓频率/约束条件

### 5. 回测配置
- 资金/手续费/滑点
- 基准选择
- 涨跌停限制

### 6. 迭代训练
- 多实验并行
- 自动超参搜索
- 模型注册与对比
- 在线/离线学习

## License

MIT
