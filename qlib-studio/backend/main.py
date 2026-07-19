"""
Qlib Studio Backend - FastAPI 主应用
提供 RESTful API 用于前端配置管理、实验调度、结果查询
"""

import os
import sys
import yaml
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# ============================================================
# 初始化 FastAPI 应用
# ============================================================

app = FastAPI(
    title="Qlib Studio API",
    description="可视化 AI 量化投资训练平台后端 API",
    version="0.1.0",
)

# CORS 支持前端开发模式
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 路径配置
# ============================================================

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "configs"
EXPERIMENT_DIR = BASE_DIR / "experiments"
TEMPLATE_DIR = BASE_DIR / "templates"
LOG_DIR = BASE_DIR / "logs"

for d in [CONFIG_DIR, EXPERIMENT_DIR, TEMPLATE_DIR, LOG_DIR]:
    d.mkdir(exist_ok=True)

# ============================================================
# Pydantic 数据模型 - 完整覆盖 Qlib 所有可配置参数
# ============================================================

class QlibInitConfig(BaseModel):
    """Qlib 初始化配置"""
    provider_uri: str = Field(default="~/.qlib/qlib_data/cn_data", description="数据路径")
    region: str = Field(default="cn", description="市场区域: cn/us")
    auto_mount: bool = Field(default=True, description="自动挂载数据")
    expression_cache: Optional[str] = Field(default=None, description="表达式缓存路径")
    calendar_cache: Optional[str] = Field(default=None, description="交易日历缓存")
    concurrent_limit: int = Field(default=6, description="并发限制")
    mongodb: Optional[Dict[str, Any]] = Field(default=None, description="MongoDB 配置")


class DataHandlerConfig(BaseModel):
    """数据处理器配置"""
    class_name: str = Field(default="Alpha158", description="因子库: Alpha158/Alpha360")
    module_path: str = Field(default="qlib.contrib.data.handler", description="模块路径")
    start_time: str = Field(default="2008-01-01", description="数据开始时间")
    end_time: str = Field(default="2024-12-31", description="数据结束时间")
    fit_start_time: str = Field(default="2008-01-01", description="拟合开始时间")
    fit_end_time: str = Field(default="2014-12-31", description="拟合结束时间")
    instruments: str = Field(default="csi300", description="股票池: csi300/csi500/all")
    infer_processors: Optional[List[Dict]] = Field(default=None, description="推断处理器链")
    learn_processors: Optional[List[Dict]] = Field(default=None, description="学习处理器链")


class DatasetConfig(BaseModel):
    """数据集配置"""
    class_name: str = Field(default="DatasetH", description="数据集类")
    module_path: str = Field(default="qlib.data.dataset", description="模块路径")
    segments: Dict[str, List[str]] = Field(
        default={"train": ["2008-01-01", "2014-12-31"],
                 "valid": ["2015-01-01", "2016-12-31"],
                 "test": ["2017-01-01", "2024-12-31"]},
        description="数据切分"
    )


class ModelConfig(BaseModel):
    """模型配置 - 支持 GBDT / DNN / Transformer 等"""
    model_type: str = Field(default="gbdt", description="模型类型: gbdt/dnn/transformer/ensemble")
    class_name: str = Field(default="LGBModel", description="模型类名")
    module_path: str = Field(default="qlib.contrib.model.gbdt", description="模型模块路径")
    # GBDT 参数
    loss: str = Field(default="mse", description="损失函数")
    learning_rate: float = Field(default=0.05, description="学习率")
    num_leaves: int = Field(default=64, description="叶子数")
    max_depth: int = Field(default=-1, description="最大深度")
    min_child_samples: int = Field(default=20, description="最小子样本数")
    feature_fraction: float = Field(default=0.8, description="特征采样比例")
    bagging_fraction: float = Field(default=0.8, description="Bagging 比例")
    bagging_freq: int = Field(default=5, description="Bagging 频率")
    num_boost_round: int = Field(default=1000, description="Boosting 轮数")
    early_stopping_rounds: int = Field(default=50, description="早停轮数")
    # DNN 参数
    hidden_size: int = Field(default=512, description="隐藏层大小 (DNN)")
    num_layers: int = Field(default=3, description="层数 (DNN)")
    dropout: float = Field(default=0.1, description="Dropout (DNN)")
    batch_size: int = Field(default=2048, description="批次大小")
    epochs: int = Field(default=100, description="训练轮数")
    optimizer: str = Field(default="adam", description="优化器")
    lr_scheduler: str = Field(default="cosine", description="学习率调度")


class StrategyConfig(BaseModel):
    """策略配置"""
    class_name: str = Field(default="TopkDropoutStrategy", description="策略类")
    module_path: str = Field(default="qlib.contrib.strategy.signal_strategy", description="策略模块")
    topk: int = Field(default=50, description="持仓数量")
    n_drop: int = Field(default=5, description="每期调出数量")
    signal_type: str = Field(default="score", description="信号类型: score/weight")
    risk_decomposition: Optional[Dict] = Field(default=None, description="风险分解配置")


class ExchangeConfig(BaseModel):
    """交易所/交易成本配置"""
    limit_threshold: float = Field(default=0.095, description="涨跌停限制")
    deal_price: str = Field(default="close", description="成交价: close/open/vwap")
    open_cost: float = Field(default=0.0005, description="买入手续费率")
    close_cost: float = Field(default=0.0015, description="卖出手续费率")
    min_cost: float = Field(default=5.0, description="最低手续费")
    trade_unit: int = Field(default=100, description="交易单位(股)")
    cancel_unit: int = Field(default=100, description="撤单单位")
    open_tax: float = Field(default=0.0, description="买入印花税")
    close_tax: float = Field(default=0.001, description="卖出印花税(印花税)")


class BacktestConfig(BaseModel):
    """回测配置"""
    start_time: str = Field(default="2017-01-01", description="回测开始时间")
    end_time: str = Field(default="2024-12-31", description="回测结束时间")
    account: float = Field(default=100000000, description="初始资金")
    benchmark: str = Field(default="SH000300", description="基准指数")
    exchange: ExchangeConfig = Field(default_factory=ExchangeConfig, description="交易所配置")


class IterationConfig(BaseModel):
    """迭代训练配置"""
    enabled: bool = Field(default=False, description="是否启用迭代训练")
    max_iterations: int = Field(default=10, description="最大迭代次数")
    param_search: str = Field(default="grid", description="参数搜索: grid/random/bayesian")
    param_space: Optional[Dict[str, Any]] = Field(default=None, description="参数搜索空间")
    early_stop_metric: str = Field(default="information_ratio", description="早停指标")
    early_stop_patience: int = Field(default=3, description="早停耐心值")
    online_learning: bool = Field(default=False, description="是否在线学习")
    retrain_frequency: str = Field(default="monthly", description="重训练频率")


class FullConfig(BaseModel):
    """完整训练配置 - 包含所有可配置项"""
    experiment_name: str = Field(default="", description="实验名称")
    description: str = Field(default="", description="实验描述")
    qlib_init: QlibInitConfig = Field(default_factory=QlibInitConfig)
    data_handler: DataHandlerConfig = Field(default_factory=DataHandlerConfig)
    dataset: DatasetConfig = Field(default_factory=DatasetConfig)
    model: ModelConfig = Field(default_factory=ModelConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    iteration: IterationConfig = Field(default_factory=IterationConfig)
    tags: List[str] = Field(default=[], description="实验标签")


# ============================================================
# 全局状态管理
# ============================================================

class ExperimentManager:
    """实验管理器 - 管理实验生命周期"""

    def __init__(self):
        self.running_experiments: Dict[str, Dict] = {}
        self.experiment_history: List[Dict] = []
        self._load_history()

    def _load_history(self):
        """加载历史实验记录"""
        history_file = EXPERIMENT_DIR / "history.json"
        if history_file.exists():
            with open(history_file, "r") as f:
                self.experiment_history = json.load(f)

    def _save_history(self):
        """保存历史实验记录"""
        history_file = EXPERIMENT_DIR / "history.json"
        with open(history_file, "w") as f:
            json.dump(self.experiment_history, f, indent=2, ensure_ascii=False)

    def create_experiment(self, config: FullConfig) -> str:
        """创建新实验"""
        exp_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        exp_dir = EXPERIMENT_DIR / exp_id
        exp_dir.mkdir(exist_ok=True)

        # 保存配置
        config_path = exp_dir / "config.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config.dict(), f, default_flow_style=False, allow_unicode=True)

        # 保存 JSON 副本
        with open(exp_dir / "config.json", "w", encoding="utf-8") as f:
            json.dump(config.dict(), f, indent=2, ensure_ascii=False)

        exp_info = {
            "id": exp_id,
            "name": config.experiment_name or exp_id,
            "description": config.description,
            "status": "created",
            "config_path": str(config_path),
            "created_at": datetime.now().isoformat(),
            "tags": config.tags,
            "metrics": {},
        }

        self.running_experiments[exp_id] = exp_info
        self.experiment_history.append(exp_info)
        self._save_history()

        return exp_id

    def get_experiment(self, exp_id: str) -> Optional[Dict]:
        """获取实验信息"""
        return self.running_experiments.get(exp_id)

    def list_experiments(self) -> List[Dict]:
        """列出所有实验"""
        return self.experiment_history

    def update_status(self, exp_id: str, status: str, metrics: Optional[Dict] = None):
        """更新实验状态"""
        if exp_id in self.running_experiments:
            self.running_experiments[exp_id]["status"] = status
            if metrics:
                self.running_experiments[exp_id]["metrics"] = metrics
            # 同步到历史
            for exp in self.experiment_history:
                if exp["id"] == exp_id:
                    exp["status"] = status
                    if metrics:
                        exp["metrics"] = metrics
                    break
            self._save_history()


# 全局实例
exp_manager = ExperimentManager()


# ============================================================
# YAML 生成器 - 将配置转为 Qlib 可执行的 YAML
# ============================================================

def generate_qlib_yaml(config: FullConfig, output_path: str) -> str:
    """将 FullConfig 转换为 Qlib qrun 格式的 YAML 文件"""

    yaml_config = {
        "qlib_init": {
            "provider_uri": config.qlib_init.provider_uri,
            "region": config.qlib_init.region,
            "auto_mount": config.qlib_init.auto_mount,
            "concurrent_limit": config.qlib_init.concurrent_limit,
        },
        "market": config.data_handler.instruments,
        "benchmark": config.backtest.benchmark,
        "data_handler_config": {
            "start_time": config.data_handler.start_time,
            "end_time": config.data_handler.end_time,
            "fit_start_time": config.data_handler.fit_start_time,
            "fit_end_time": config.data_handler.fit_end_time,
            "instruments": config.data_handler.instruments,
        },
        "task": {
            "model": {
                "class": config.model.class_name,
                "module_path": config.model.module_path,
                "kwargs": _build_model_kwargs(config.model),
            },
            "dataset": {
                "class": config.dataset.class_name,
                "module_path": config.dataset.module_path,
                "kwargs": {
                    "handler": {
                        "class": config.data_handler.class_name,
                        "module_path": config.data_handler.module_path,
                        "kwargs": {
                            "start_time": config.data_handler.start_time,
                            "end_time": config.data_handler.end_time,
                            "fit_start_time": config.data_handler.fit_start_time,
                            "fit_end_time": config.data_handler.fit_end_time,
                            "instruments": config.data_handler.instruments,
                        },
                    },
                    "segments": config.dataset.segments,
                },
            },
            "record": [
                {
                    "class": "SignalRecord",
                    "module_path": "qlib.workflow.record_temp",
                },
                {
                    "class": "PortAnaRecord",
                    "module_path": "qlib.workflow.record_temp",
                    "kwargs": {
                        "config": {
                            "strategy": {
                                "class": config.strategy.class_name,
                                "module_path": config.strategy.module_path,
                                "kwargs": {
                                    "topk": config.strategy.topk,
                                    "n_drop": config.strategy.n_drop,
                                },
                            },
                            "backtest": {
                                "start_time": config.backtest.start_time,
                                "end_time": config.backtest.end_time,
                                "account": config.backtest.account,
                                "benchmark": config.backtest.benchmark,
                                "exchange_kwargs": config.backtest.exchange.dict(),
                            },
                        }
                    },
                },
            ],
        },
    }

    # 处理迭代训练
    if config.iteration.enabled:
        yaml_config["task"]["model"]["kwargs"]["iterations"] = config.iteration.max_iterations

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_config, f, default_flow_style=False, allow_unicode=True)

    return output_path


def _build_model_kwargs(model_cfg: ModelConfig) -> Dict[str, Any]:
    """根据模型类型构建 kwargs"""
    if model_cfg.model_type == "gbdt":
        return {
            "loss": model_cfg.loss,
            "learning_rate": model_cfg.learning_rate,
            "num_leaves": model_cfg.num_leaves,
            "max_depth": model_cfg.max_depth,
            "min_child_samples": model_cfg.min_child_samples,
            "feature_fraction": model_cfg.feature_fraction,
            "bagging_fraction": model_cfg.bagging_fraction,
            "bagging_freq": model_cfg.bagging_freq,
            "num_boost_round": model_cfg.num_boost_round,
            "early_stopping_rounds": model_cfg.early_stopping_rounds,
        }
    elif model_cfg.model_type == "dnn":
        return {
            "hidden_size": model_cfg.hidden_size,
            "num_layers": model_cfg.num_layers,
            "dropout": model_cfg.dropout,
            "batch_size": model_cfg.batch_size,
            "epochs": model_cfg.epochs,
            "optimizer": model_cfg.optimizer,
            "lr_scheduler": model_cfg.lr_scheduler,
        }
    else:
        return {
            "learning_rate": model_cfg.learning_rate,
            "batch_size": model_cfg.batch_size,
            "epochs": model_cfg.epochs,
        }


# ============================================================
# 训练执行器 - 运行 Qlib 训练
# ============================================================

def run_experiment(exp_id: str, config: FullConfig):
    """后台执行实验"""
    exp_dir = EXPERIMENT_DIR / exp_id
    yaml_path = exp_dir / "workflow.yaml"

    # 生成 YAML
    generate_qlib_yaml(config, str(yaml_path))

    # 更新状态
    exp_manager.update_status(exp_id, "running")

    # 构建日志路径
    log_path = exp_dir / "train.log"

    try:
        # 使用 qrun 执行
        with open(log_path, "w") as log_file:
            process = subprocess.Popen(
                ["qrun", str(yaml_path)],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(exp_dir),
            )

            # 等待完成
            process.wait()

            if process.returncode == 0:
                exp_manager.update_status(exp_id, "completed")
            else:
                exp_manager.update_status(exp_id, "failed")

    except Exception as e:
        exp_manager.update_status(exp_id, "error")
        with open(log_path, "a") as f:
            f.write(f"\n[ERROR] {str(e)}\n")


# ============================================================
# API 路由
# ============================================================

@app.get("/")
def root():
    return {
        "name": "Qlib Studio API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "config_templates": "/api/config/templates",
            "create_experiment": "POST /api/experiments",
            "list_experiments": "GET /api/experiments",
            "get_experiment": "GET /api/experiments/{exp_id}",
            "start_experiment": "POST /api/experiments/{exp_id}/start",
            "get_metrics": "GET /api/experiments/{exp_id}/metrics",
            "get_logs": "GET /api/experiments/{exp_id}/logs",
            "compare_experiments": "POST /api/experiments/compare",
            "model_registry": "GET /api/models",
        }
    }


# ---------- 配置模板 ----------

@app.get("/api/config/templates")
def get_config_templates():
    """获取预置配置模板"""
    templates = {
        "lightgbm_alpha158_csi300": {
            "name": "LightGBM + Alpha158 (沪深300)",
            "description": "经典 GBDT 模型 + 158 因子，适合入门",
            "config": FullConfig(
                experiment_name="LightGBM_Alpha158_CSI300",
                model=ModelConfig(model_type="gbdt", class_name="LGBModel"),
                data_handler=DataHandlerConfig(class_name="Alpha158", instruments="csi300"),
            ).dict()
        },
        "lightgbm_alpha360_csi500": {
            "name": "LightGBM + Alpha360 (沪深500)",
            "description": "360 因子 + GBDT，更丰富的特征空间",
            "config": FullConfig(
                experiment_name="LightGBM_Alpha360_CSI500",
                model=ModelConfig(model_type="gbdt", class_name="LGBModel",
                                num_leaves=128, learning_rate=0.03),
                data_handler=DataHandlerConfig(class_name="Alpha360", instruments="csi500"),
            ).dict()
        },
        "mlp_dnn_csi300": {
            "name": "MLP 深度学习 (沪深300)",
            "description": "PyTorch MLP 模型，适合大数据量",
            "config": FullConfig(
                experiment_name="MLP_DNN_CSI300",
                model=ModelConfig(
                    model_type="dnn",
                    class_name="MLPModel",
                    module_path="qlib.contrib.model.pytorch",
                    hidden_size=512,
                    num_layers=3,
                    dropout=0.2,
                    epochs=200,
                ),
            ).dict()
        },
        "transformer_csi300": {
            "name": "Transformer 时序模型 (沪深300)",
            "description": "基于 Transformer 的时序预测模型",
            "config": FullConfig(
                experiment_name="Transformer_CSI300",
                model=ModelConfig(
                    model_type="transformer",
                    class_name="TransformerModel",
                    module_path="qlib.contrib.model.pytorch_transformer",
                    hidden_size=256,
                    num_layers=4,
                    epochs=150,
                ),
            ).dict()
        },
        "ensemble_csi300": {
            "name": "集成模型 (沪深300)",
            "description": "GBDT + DNN 集成预测",
            "config": FullConfig(
                experiment_name="Ensemble_CSI300",
                model=ModelConfig(
                    model_type="ensemble",
                    class_name="EnsembleModel",
                    module_path="qlib.contrib.model.ensemble",
                ),
                iteration=IterationConfig(enabled=True, max_iterations=5),
            ).dict()
        },
    }
    return templates


@app.get("/api/config/default")
def get_default_config():
    """获取默认完整配置"""
    return FullConfig().dict()


@app.post("/api/config/validate")
def validate_config(config: FullConfig):
    """验证配置合法性"""
    errors = []

    # 时间校验
    if config.data_handler.start_time >= config.data_handler.end_time:
        errors.append("数据开始时间必须早于结束时间")

    # 切分校验
    for seg_name, seg_range in config.dataset.segments.items():
        if len(seg_range) != 2:
            errors.append(f"数据切分 {seg_name} 格式错误")
        if seg_range[0] >= seg_range[1]:
            errors.append(f"数据切分 {seg_name} 开始时间必须早于结束时间")

    # 回测时间必须在数据范围内
    if config.backtest.start_time < config.data_handler.start_time:
        errors.append("回测开始时间不能早于数据开始时间")

    # 模型参数校验
    if config.model.model_type == "gbdt":
        if config.model.num_leaves <= 1:
            errors.append("num_leaves 必须大于 1")
        if config.model.learning_rate <= 0:
            errors.append("learning_rate 必须大于 0")

    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True, "errors": []}


# ---------- 实验管理 ----------

@app.post("/api/experiments")
def create_experiment(config: FullConfig, background_tasks: BackgroundTasks):
    """创建新实验"""
    # 验证配置
    if not config.experiment_name:
        config.experiment_name = f"Experiment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    exp_id = exp_manager.create_experiment(config)
    return {"exp_id": exp_id, "status": "created", "message": "实验创建成功"}


@app.get("/api/experiments")
def list_experiments(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """列出实验"""
    experiments = exp_manager.list_experiments()

    if status:
        experiments = [e for e in experiments if e.get("status") == status]
    if tag:
        experiments = [e for e in experiments if tag in e.get("tags", [])]

    total = len(experiments)
    experiments = experiments[offset:offset + limit]

    return {"total": total, "experiments": experiments}


@app.get("/api/experiments/{exp_id}")
def get_experiment(exp_id: str):
    """获取实验详情"""
    exp = exp_manager.get_experiment(exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")

    # 读取配置文件
    exp_dir = EXPERIMENT_DIR / exp_id
    config_path = exp_dir / "config.json"
    if config_path.exists():
        with open(config_path, "r") as f:
            exp["config"] = json.load(f)

    return exp


@app.post("/api/experiments/{exp_id}/start")
def start_experiment(exp_id: str, background_tasks: BackgroundTasks):
    """启动实验"""
    exp = exp_manager.get_experiment(exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")

    # 读取配置
    exp_dir = EXPERIMENT_DIR / exp_id
    config_path = exp_dir / "config.json"
    with open(config_path, "r") as f:
        config_dict = json.load(f)

    config = FullConfig(**config_dict)

    # 后台执行
    background_tasks.add_task(run_experiment, exp_id, config)

    return {"exp_id": exp_id, "status": "started", "message": "实验已启动"}


@app.post("/api/experiments/{exp_id}/stop")
def stop_experiment(exp_id: str):
    """停止实验"""
    exp = exp_manager.get_experiment(exp_id)
    if not exp:
        raise HTTPException(status_code=404, detail="实验不存在")

    exp_manager.update_status(exp_id, "stopped")
    return {"exp_id": exp_id, "status": "stopped"}


@app.delete("/api/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    """删除实验"""
    exp_dir = EXPERIMENT_DIR / exp_id
    if exp_dir.exists():
        shutil.rmtree(exp_dir)

    # 从管理中移除
    exp_manager.running_experiments.pop(exp_id, None)
    exp_manager.experiment_history = [
        e for e in exp_manager.experiment_history if e["id"] != exp_id
    ]
    exp_manager._save_history()

    return {"message": "实验已删除"}


# ---------- 指标与日志 ----------

@app.get("/api/experiments/{exp_id}/metrics")
def get_experiment_metrics(exp_id: str):
    """获取实验回测指标"""
    exp_dir = EXPERIMENT_DIR / exp_id

    # 尝试读取 Qlib 生成的指标文件
    metrics_file = exp_dir / "metrics.json"
    if metrics_file.exists():
        with open(metrics_file, "r") as f:
            return json.load(f)

    # 尝试从 mlruns 读取
    mlruns_dir = exp_dir / "mlruns"
    if mlruns_dir.exists():
        # 解析 MLflow 格式的指标
        return {"source": "mlflow", "path": str(mlruns_dir)}

    return {"message": "指标尚未生成", "status": "pending"}


@app.get("/api/experiments/{exp_id}/logs")
def get_experiment_logs(exp_id: str, tail: int = 200):
    """获取实验日志"""
    log_path = EXPERIMENT_DIR / exp_id / "train.log"
    if not log_path.exists():
        return {"logs": "", "message": "日志文件不存在"}

    with open(log_path, "r") as f:
        lines = f.readlines()

    # 返回最后 N 行
    recent_lines = lines[-tail:] if len(lines) > tail else lines
    return {"logs": "".join(recent_lines), "total_lines": len(lines)}


@app.get("/api/experiments/{exp_id}/portfolio")
def get_portfolio(exp_id: str):
    """获取组合净值曲线数据"""
    exp_dir = EXPERIMENT_DIR / exp_id

    # 查找回测报告
    for f in exp_dir.rglob("report_normal_1day.pkl"):
        import pandas as pd
        df = pd.read_pickle(f)
        return {
            "dates": df.index.strftime("%Y-%m-%d").tolist(),
            "portfolio_value": df.get("portfolio_value", df.iloc[:, 0]).tolist(),
            "return": df.get("return", "").tolist() if "return" in df else None,
        }

    return {"message": "回测结果尚未生成"}


# ---------- 实验对比 ----------

@app.post("/api/experiments/compare")
def compare_experiments(exp_ids: List[str]):
    """对比多个实验的指标"""
    results = []
    for exp_id in exp_ids:
        exp = exp_manager.get_experiment(exp_id)
        if exp:
            metrics_file = EXPERIMENT_DIR / exp_id / "metrics.json"
            metrics = {}
            if metrics_file.exists():
                with open(metrics_file, "r") as f:
                    metrics = json.load(f)

            results.append({
                "exp_id": exp_id,
                "name": exp.get("name", exp_id),
                "status": exp.get("status"),
                "metrics": metrics,
            })

    return {"comparison": results}


# ---------- 模型注册中心 ----------

@app.get("/api/models")
def list_models():
    """列出已训练的模型"""
    models = []
    for exp_dir in EXPERIMENT_DIR.iterdir():
        if exp_dir.is_dir():
            model_file = exp_dir / "trained_model.pkl"
            config_file = exp_dir / "config.json"
            if model_file.exists():
                info = {
                    "exp_id": exp_dir.name,
                    "model_path": str(model_file),
                    "size_mb": round(model_file.stat().st_size / 1024 / 1024, 2),
                }
                if config_file.exists():
                    with open(config_file, "r") as f:
                        cfg = json.load(f)
                        info["model_type"] = cfg.get("model", {}).get("model_type")
                        info["experiment_name"] = cfg.get("experiment_name")

                models.append(info)

    return {"models": models}


@app.post("/api/models/{exp_id}/register")
def register_model(exp_id: str, model_name: str):
    """注册模型到模型仓库"""
    exp_dir = EXPERIMENT_DIR / exp_id
    model_file = exp_dir / "trained_model.pkl"

    if not model_file.exists():
        raise HTTPException(status_code=404, detail="模型文件不存在")

    # 复制到模型仓库
    model_repo = BASE_DIR / "model_registry"
    model_repo.mkdir(exist_ok=True)

    target = model_repo / f"{model_name}.pkl"
    shutil.copy2(model_file, target)

    # 记录注册信息
    registry_info = model_repo / "registry.json"
    registry = []
    if registry_info.exists():
        with open(registry_info, "r") as f:
            registry = json.load(f)

    registry.append({
        "name": model_name,
        "exp_id": exp_id,
        "registered_at": datetime.now().isoformat(),
        "path": str(target),
    })

    with open(registry_info, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    return {"message": f"模型 {model_name} 注册成功", "path": str(target)}


# ---------- 迭代训练 ----------

@app.post("/api/experiments/{exp_id}/iterate")
def start_iteration(exp_id: str, config: FullConfig, background_tasks: BackgroundTasks):
    """启动迭代训练"""
    if not config.iteration.enabled:
        config.iteration.enabled = True

    exp_manager.update_status(exp_id, "iterating")

    # 后台执行迭代
    background_tasks.add_task(run_iteration, exp_id, config)

    return {"exp_id": exp_id, "status": "iterating", "message": "迭代训练已启动"}


def run_iteration(exp_id: str, config: FullConfig):
    """执行迭代训练逻辑"""
    exp_dir = EXPERIMENT_DIR / exp_id
    best_metrics = None
    best_iter = 0

    for i in range(config.iteration.max_iterations):
        iter_dir = exp_dir / f"iter_{i+1}"
        iter_dir.mkdir(exist_ok=True)

        # 根据搜索策略调整参数
        adjusted_config = _adjust_params(config, i)
        yaml_path = iter_dir / "workflow.yaml"
        generate_qlib_yaml(adjusted_config, str(yaml_path))

        # 执行训练
        log_path = iter_dir / "train.log"
        try:
            result = subprocess.run(
                ["qrun", str(yaml_path)],
                capture_output=True,
                text=True,
                cwd=str(iter_dir),
                timeout=3600,  # 1小时超时
            )

            with open(log_path, "w") as f:
                f.write(result.stdout)
                f.write(result.stderr)

        except subprocess.TimeoutExpired:
            continue

        # 读取指标并比较
        metrics_file = iter_dir / "metrics.json"
        if metrics_file.exists():
            with open(metrics_file, "r") as f:
                metrics = json.load(f)

            # 检查早停
            if _is_better(metrics, best_metrics, config.iteration.early_stop_metric):
                best_metrics = metrics
                best_iter = i + 1

            if i - best_iter >= config.iteration.early_stop_patience:
                break

    exp_manager.update_status(exp_id, "completed", best_metrics)


def _adjust_params(config: FullConfig, iteration: int) -> FullConfig:
    """根据迭代次数调整参数（简化版网格搜索）"""
    cfg = config.copy()

    if config.iteration.param_search == "grid":
        # 简单的网格搜索逻辑
        lr_options = [0.01, 0.03, 0.05, 0.08, 0.1]
        leaves_options = [32, 64, 128, 256]

        idx = iteration
        cfg.model.learning_rate = lr_options[idx % len(lr_options)]
        cfg.model.num_leaves = leaves_options[(idx // len(lr_options)) % len(leaves_options)]

    elif config.iteration.param_search == "random":
        import random
        cfg.model.learning_rate = round(random.uniform(0.01, 0.1), 4)
        cfg.model.num_leaves = random.choice([32, 64, 128, 256])

    return cfg


def _is_better(current: Dict, best: Optional[Dict], metric: str) -> bool:
    """判断当前指标是否优于最佳"""
    if best is None:
        return True
    current_val = current.get(metric, 0)
    best_val = best.get(metric, 0)
    return current_val > best_val


# ---------- 系统状态 ----------

@app.get("/api/system/status")
def system_status():
    """获取系统状态"""
    return {
        "running_experiments": len([e for e in exp_manager.running_experiments.values()
                                   if e["status"] == "running"]),
        "total_experiments": len(exp_manager.experiment_history),
        "disk_usage": _get_disk_usage(),
        "qlib_data_path": str(Path("~/.qlib/qlib_data").expanduser()),
    }


def _get_disk_usage() -> Dict:
    """获取磁盘使用情况"""
    import shutil
    total, used, free = shutil.disk_usage("/")
    return {
        "total_gb": round(total / 1024**3, 2),
        "used_gb": round(used / 1024**3, 2),
        "free_gb": round(free / 1024**3, 2),
    }


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
