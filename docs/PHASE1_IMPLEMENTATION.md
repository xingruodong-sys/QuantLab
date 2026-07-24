# Phase 1: Rolling 训练 + 每日预测 + 定时任务 实现指南

## 📦 已完成的模块

### 1. Rolling 训练引擎 (`backend/rolling_trainer.py`)
**功能特性：**
- ✅ 支持 Rolling Window（固定窗口）和 Expanding Window（扩展窗口）两种模式
- ✅ 自动生成滚动训练周期
- ✅ 批量训练所有周期并保存模型
- ✅ 自动提取和聚合训练指标（IC、Rank IC、Sharpe 等）
- ✅ 支持断点续训（跳过已完成的周期）
- ✅ 提供 CLI 接口和 Python API

**使用方法：**

```bash
# CLI 方式运行
python backend/rolling_trainer.py \
  --experiment-dir ./experiments \
  --window-size 630 \
  --step-size 252 \
  --mode rolling \
  --calendar-start 2018-01-01 \
  --calendar-end 2024-12-31 \
  --config ./configs/example_full.yaml \
  --force

# Python API 方式
from rolling_trainer import RollingTrainer

trainer = RollingTrainer(
    experiment_dir="./experiments",
    window_size=630,
    step_size=252,
    mode="rolling"
)

# 生成周期
trainer.generate_periods("2018-01-01", "2024-12-31")

# 加载配置并训练
import yaml
with open("./configs/example_full.yaml", "r") as f:
    config = yaml.safe_load(f)

results = trainer.train_all_periods(config)

# 获取最佳模型
best_model_path = trainer.get_best_model(metric="ic")
latest_model_path = trainer.get_latest_model()
```

**输出结构：**
```
experiments/
└── rolling_experiments/
    ├── rolling_config.json      # 滚动配置
    ├── periods.json             # 周期信息
    ├── history.json             # 训练历史
    ├── roll_20241231/           # 第一个周期
    │   ├── config.yaml
    │   ├── train.log
    │   ├── trained_model.pkl
    │   └── metrics.json
    ├── roll_20231231/           # 第二个周期
    └── ...
```

---

### 2. 每日预测流水线 (`backend/daily_prediction.py`)
**功能特性：**
- ✅ 支持多数据源（AKShare / Tushare / Qlib）
- ✅ 自动计算技术指标特征（RSI、MACD、布林带等）
- ✅ 加载模型进行推理预测
- ✅ 生成交易信号（买入/卖出/持有）
- ✅ 保存信号到多种格式（JSON / CSV / Parquet）
- ✅ 完整的 Pipeline 流程和错误处理

**使用方法：**

```bash
# CLI 方式运行
python backend/daily_prediction.py \
  --model-dir ./experiments \
  --date 2024-12-31 \
  --universe csi300 \
  --top-k 50 \
  --n-drop 5 \
  --output-dir ./predictions \
  --provider akshare

# Python API 方式
from daily_prediction import DailyPredictor
from pathlib import Path

predictor = DailyPredictor(
    model_dir=Path("./experiments"),
    data_provider="akshare",
    output_dir=Path("./predictions")
)

# 运行完整流水线
results = predictor.run_full_pipeline(
    date=None,  # 自动使用最近交易日
    universe="csi300",
    top_k=50,
    n_drop=5,
    exp_id=None  # 自动查找最新模型
)

# 单独步骤调用
model = predictor.load_model(exp_id="exp_20241201_120000")
data = predictor.fetch_latest_data(date="2024-12-31", universe="csi300")
features = predictor.calculate_features(data)
predictions = predictor.predict(model, features)
signals = predictor.generate_signals(predictions, top_k=50)
predictor.save_signals(signals, date="2024-12-31")
```

**输出示例：**
```json
{
  "buy": ["000001", "000002", "600000", ...],
  "sell": ["000895", "002049", ...],
  "hold": [...],
  "generated_at": "2024-12-31T09:00:00",
  "total_stocks": 300
}
```

---

### 3. 定时任务调度器 (`backend/task_scheduler.py`)
**功能特性：**
- ✅ 基于 APScheduler 实现
- ✅ 支持 Cron 表达式配置
- ✅ 预置滚动训练、每日预测、数据更新任务
- ✅ 任务执行监控和历史记录
- ✅ 支持手动触发、暂停、恢复任务
- ✅ 失败重试和容错机制

**配置文件：** `configs/scheduler_config.yaml`

**使用方法：**

```bash
# 启动调度器（阻塞模式）
python backend/task_scheduler.py \
  --config ./configs/scheduler_config.yaml \
  --experiment-dir ./experiments \
  --model-dir ./experiments \
  --output-dir ./predictions \
  --action start

# 查看任务状态
python backend/task_scheduler.py \
  --config ./configs/scheduler_config.yaml \
  --action status

# 手动触发任务
python backend/task_scheduler.py \
  --config ./configs/scheduler_config.yaml \
  --action run \
  --task daily_predict
```

**Python API：**
```python
from task_scheduler import TaskScheduler

scheduler = TaskScheduler(
    config_path="./configs/scheduler_config.yaml",
    scheduler_type="background"
)

# 注册任务
scheduler.register_rolling_train(
    experiment_dir="./experiments",
    config_path="./configs/example_full.yaml",
    calendar_start="2018-01-01",
    calendar_end="2024-12-31"
)

scheduler.register_daily_predict(
    model_dir="./experiments",
    output_dir="./predictions",
    universe="csi300",
    top_k=50
)

# 启动调度器
scheduler.start(blocking=False)

# 查看状态
status = scheduler.get_all_status()
print(status)

# 手动触发
scheduler.run_now("daily_predict")

# 暂停/恢复
scheduler.pause_task("rolling_train")
scheduler.resume_task("rolling_train")
```

---

## 🔧 安装依赖

```bash
cd qlib-studio/backend

# 安装所有依赖
pip install -r requirements.txt

# 或单独安装新增依赖
pip install APScheduler>=3.10.0 akshare>=1.10.0 tushare>=1.2.0
```

---

## 📋 典型工作流程

### 场景 1：首次部署，进行历史回测训练

```bash
# 1. 准备配置文件
cp configs/example_full.yaml configs/my_strategy.yaml
# 编辑 my_strategy.yaml 调整参数

# 2. 运行滚动训练
python backend/rolling_trainer.py \
  --experiment-dir ./experiments \
  --window-size 630 \
  --step-size 252 \
  --mode rolling \
  --calendar-start 2018-01-01 \
  --calendar-end 2024-12-31 \
  --config configs/my_strategy.yaml

# 3. 查看训练结果
ls -la experiments/rolling_experiments/
cat experiments/rolling_experiments/history.json
```

### 场景 2：每日自动预测

```bash
# 1. 启动调度器（后台运行）
nohup python backend/task_scheduler.py \
  --config configs/scheduler_config.yaml \
  --experiment-dir ./experiments \
  --model-dir ./experiments \
  --output-dir ./predictions \
  --action start > scheduler.log 2>&1 &

# 2. 查看日志
tail -f scheduler.log

# 3. 查看生成的信号
ls -la predictions/
cat predictions/signals_2024-12-31_*.json
```

### 场景 3：手动执行单次预测

```bash
# 使用最新模型进行预测
python backend/daily_prediction.py \
  --model-dir ./experiments \
  --universe csi300 \
  --top-k 50 \
  --output-dir ./predictions

# 查看结果
cat predictions/pipeline_result_*.json
```

---

## 📊 监控与运维

### 查看任务执行历史
```python
import json
with open("./scheduler_history.json", "r") as f:
    history = json.load(f)
    for record in history[-10:]:
        print(f"{record['executed_at']}: {record['job_id']} - {record['status']}")
```

### 查看滚动训练指标
```python
import json
with open("./experiments/rolling_experiments/history.json", "r") as f:
    histories = json.load(f)
    latest = histories[-1]
    print("Metrics Summary:")
    for k, v in latest['results']['metrics_summary'].items():
        print(f"  {k}: {v}")
```

---

## ⚠️ 注意事项

1. **数据源配置**
   - AKShare：免费，无需配置，但稳定性一般
   - Tushare：需要 token，设置环境变量 `export TUSHARE_TOKEN=your_token`
   - Qlib：需要预先下载数据 `python scripts/get_data.py`

2. **交易日历**
   - 当前使用简化版工作日日历
   - 生产环境建议从 Qlib 获取真实交易日历

3. **特征计算**
   - 当前实现了基础技术指标
   - 可根据策略需求扩展更多因子

4. **模型兼容性**
   - 支持 Qlib 训练的 LightGBM/XGBoost/CatBoost 模型
   - 支持 sklearn 兼容的模型接口

5. **定时任务时区**
   - 默认使用 Asia/Shanghai 时区
   - 确保服务器时区配置正确

---

## 🚀 下一步（Phase 2）

完成 Phase 1 后，可以考虑：

1. **实时数据接入** - 对接 Level2 行情、分钟线数据
2. **监控告警系统** - Prometheus + Grafana + 钉钉/微信告警
3. **模型漂移检测** - PSI/KS统计量、IC 衰减监控
4. **组合优化器** - 均值方差优化、风险模型
5. **券商交易接口** - 对接实盘交易系统

---

## 📞 问题排查

### 常见问题

**Q: 滚动训练报错 "qrun: command not found"**
```bash
# 确保 Qlib 已正确安装
pip install pyqlib
which qrun
```

**Q: AKShare 数据获取失败**
```bash
# 升级 AKShare
pip install --upgrade akshare

# 检查网络连接
ping www.akshare.xyz
```

**Q: 定时任务不执行**
```bash
# 检查调度器日志
tail -f scheduler.log

# 验证 cron 表达式
# 访问 https://crontab.guru/ 验证表达式
```

**Q: 预测结果为空**
```bash
# 检查模型文件是否存在
ls -la experiments/*/trained_model.pkl

# 检查数据源是否正常
python -c "import akshare as ak; print(ak.__version__)"
```

---

祝部署顺利！🎉
