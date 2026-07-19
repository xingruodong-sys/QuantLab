# Qlib Studio 架构文档

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                    前端 (React + Ant Design)                  │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ 仪表盘    │  │ 配置编辑器    │  │ 实验管理           │  │
│  │ Dashboard │  │ ConfigEditor │  │ ExperimentList     │  │
│  └──────────┘  └──────────────┘  └────────────────────┘  │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │ 回测分析  │  │ 模型仓库     │  │ 实验详情           │  │
│  │ Backtest │  │ ModelRegistry│  │ ExperimentDetail  │  │
│  └──────────┘  └──────────────┘  └────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP/REST API
                           │ (Axios)
┌──────────────────────────▼──────────────────────────────────┐
│                  后端 (FastAPI)                              │
│                                                              │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐      │
│  │ API Routes │  │ YAML Gen   │  │ Exp Manager      │      │
│  │ /api/*     │─▶│ Qlib YAML  │─▶│ Experiment Mgr   │      │
│  └────────────┘  └────────────┘  └──────────────────┘      │
│         │              │                    │                 │
│         ▼              ▼                    ▼                 │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────┐    │
│  │ Pydantic   │  │ Subprocess │  │ SQLite/JSON Store │    │
│  │ Models     │  │ qrun       │  │ History & State   │    │
│  └────────────┘  └────────────┘  └──────────────────┘      │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Qlib 训练引擎                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │
│  │ Data    │  │ Model   │  │ Strategy│  │ Backtest    │  │
│  │ Handler │─▶│ Train   │─▶│ Signal  │─▶│ Simulator  │  │
│  └─────────┘  └─────────┘  └─────────┘  └─────────────┘  │
│                                                              │
│  数据: Alpha158/360 | 模型: GBDT/DNN/Transformer            │
│  策略: TopK Dropout | 回测: 成本/滑点/涨跌停                 │
└─────────────────────────────────────────────────────────────┘
```

## 核心流程

### 1. 配置阶段
```
用户在前端配置 → Form 提交 → API 接收 → Pydantic 校验 → 存储为 JSON + YAML
```

### 2. 训练阶段
```
用户点击启动 → 后台任务 → subprocess 调用 qrun → Qlib 执行训练 → 输出指标
```

### 3. 回测阶段
```
模型预测 → 信号生成 → 策略选股 → 模拟交易 → 净值曲线 + 指标报告
```

### 4. 迭代阶段
```
多组超参 → 并行训练 → 指标对比 → 自动选优 → 模型注册
```

## API 端点一览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config/default` | 获取默认配置 |
| GET | `/api/config/templates` | 获取预置模板 |
| POST | `/api/config/validate` | 验证配置 |
| POST | `/api/experiments` | 创建实验 |
| GET | `/api/experiments` | 列出实验 |
| GET | `/api/experiments/{id}` | 实验详情 |
| POST | `/api/experiments/{id}/start` | 启动实验 |
| POST | `/api/experiments/{id}/stop` | 停止实验 |
| DELETE | `/api/experiments/{id}` | 删除实验 |
| GET | `/api/experiments/{id}/metrics` | 获取指标 |
| GET | `/api/experiments/{id}/logs` | 获取日志 |
| GET | `/api/experiments/{id}/portfolio` | 获取净值 |
| POST | `/api/experiments/compare` | 对比实验 |
| POST | `/api/experiments/{id}/iterate` | 迭代训练 |
| GET | `/api/models` | 模型列表 |
| POST | `/api/models/{id}/register` | 注册模型 |
| GET | `/api/system/status` | 系统状态 |

## 可配置参数全表

### Qlib 初始化
| 参数 | 默认值 | 说明 |
|------|--------|------|
| provider_uri | ~/.qlib/qlib_data/cn_data | 数据路径 |
| region | cn | 市场区域 (cn/us) |
| auto_mount | true | 自动挂载 |
| concurrent_limit | 6 | 并发限制 |

### 数据处理器
| 参数 | 默认值 | 说明 |
|------|--------|------|
| class_name | Alpha158 | 因子库类 |
| start_time | 2008-01-01 | 数据开始 |
| end_time | 2024-12-31 | 数据结束 |
| fit_start_time | 2008-01-01 | 拟合开始 |
| fit_end_time | 2014-12-31 | 拟合结束 |
| instruments | csi300 | 股票池 |

### 模型 (GBDT)
| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| loss | mse | mse/mae/binary | 损失函数 |
| learning_rate | 0.05 | 0.001~0.3 | 学习率 |
| num_leaves | 64 | 2~1024 | 叶子数 |
| max_depth | -1 | -1~50 | 最大深度 |
| min_child_samples | 20 | 1~1000 | 最小样本 |
| feature_fraction | 0.8 | 0.1~1.0 | 特征采样 |
| bagging_fraction | 0.8 | 0.1~1.0 | 样本采样 |
| num_boost_round | 1000 | 10~10000 | 轮数 |
| early_stopping_rounds | 50 | 5~500 | 早停 |

### 模型 (DNN)
| 参数 | 默认值 | 范围 | 说明 |
|------|--------|------|------|
| hidden_size | 512 | 32~4096 | 隐藏层 |
| num_layers | 3 | 1~20 | 层数 |
| dropout | 0.1 | 0~0.9 | Dropout |
| batch_size | 2048 | 16~8192 | 批大小 |
| epochs | 100 | 1~1000 | 训练轮数 |
| optimizer | adam | adam/sgd | 优化器 |

### 策略
| 参数 | 默认值 | 说明 |
|------|--------|------|
| class_name | TopkDropoutStrategy | 策略类 |
| topk | 50 | 持仓数 |
| n_drop | 5 | 调出数 |
| signal_type | score | 信号类型 |

### 回测
| 参数 | 默认值 | 说明 |
|------|--------|------|
| start_time | 2017-01-01 | 回测开始 |
| end_time | 2024-12-31 | 回测结束 |
| account | 1亿 | 初始资金 |
| benchmark | SH000300 | 基准指数 |
| limit_threshold | 0.095 | 涨跌停 |
| deal_price | close | 成交价 |
| open_cost | 0.0005 | 买入费率 |
| close_cost | 0.0015 | 卖出费率 |

### 迭代训练
| 参数 | 默认值 | 说明 |
|------|--------|------|
| enabled | false | 是否启用 |
| max_iterations | 10 | 最大迭代 |
| param_search | grid | 搜索策略 |
| early_stop_metric | IR | 早停指标 |
| early_stop_patience | 3 | 耐心值 |

## 扩展指南

### 添加新模型
1. 在 `ModelConfig` 中添加新参数
2. 在 `_build_model_kwargs` 中添加转换逻辑
3. 在前端 `ConfigEditor` 中添加表单字段

### 添加新策略
1. 在 `StrategyConfig` 中扩展参数
2. 在 YAML 生成器中添加策略配置
3. 前端下拉框添加选项

### 添加数据源
1. 实现自定义 DataHandler
2. 在 `data_handler_config` 中指定模块路径
3. 前端添加数据源选项

## 部署

### Docker 一键部署
```bash
docker-compose -f docker/docker-compose.yml up -d
```

### 手动部署
```bash
# 后端
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run build
# 将 dist/ 部署到 Nginx
```

## 路线图

- [x] 基础配置 + 训练 + 回测
- [x] 多实验管理
- [x] 迭代训练
- [ ] Optuna 超参自动优化
- [ ] 分布式训练支持
- [ ] 实时行情接入
- [ ] 更多因子库 (Alpha360 完整支持)
- [ ] 风险模型集成
- [ ] 组合优化器
- [ ] 多用户权限管理
- [ ] 实验报告导出 (PDF)
- [ ] 微信/邮件通知
