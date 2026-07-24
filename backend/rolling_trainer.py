"""
Rolling Training Engine - 滚动窗口训练引擎
支持 Expanding Window / Rolling Window 时间序列交叉验证
用于生产环境的模型定期重训练
"""

import os
import sys
import yaml
import json
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import pandas as pd
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class RollingPeriod:
    """定义一个滚动训练周期"""
    period_id: str
    train_start: str
    train_end: str
    valid_start: str
    valid_end: str
    test_start: str
    test_end: str
    status: str = "pending"  # pending, running, completed, failed
    model_path: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class RollingTrainer:
    """
    滚动训练引擎
    
    支持两种模式：
    1. Rolling Window: 固定窗口长度，逐步向前滚动
    2. Expanding Window: 起始时间固定，结束时间逐步向后扩展
    
    使用场景：
    - 每周/每月重训练模型
    - 测试模型在不同市场周期的表现
    - 构建模型 ensemble
    """
    
    def __init__(
        self,
        experiment_dir: Path,
        window_size: int = 252 * 3,  # 默认 3 年交易日
        step_size: int = 252,         # 默认 1 年步长
        valid_size: int = 252,        # 验证集长度
        test_size: int = 252,         # 测试集长度
        mode: str = "rolling",        # rolling / expanding
        min_periods: int = 3          # 最少生成多少个周期
    ):
        """
        Args:
            experiment_dir: 实验目录
            window_size: 训练窗口大小（交易日天数）
            step_size: 滚动步长（交易日天数）
            valid_size: 验证集大小
            test_size: 测试集大小
            mode: 滚动模式 (rolling/expanding)
            min_periods: 最少生成的周期数
        """
        self.experiment_dir = Path(experiment_dir)
        self.window_size = window_size
        self.step_size = step_size
        self.valid_size = valid_size
        self.test_size = test_size
        self.mode = mode
        self.min_periods = min_periods
        
        # 创建滚动训练目录
        self.rolling_dir = self.experiment_dir / "rolling_experiments"
        self.rolling_dir.mkdir(exist_ok=True)
        
        # 保存配置
        self.config_file = self.rolling_dir / "rolling_config.json"
        self.periods_file = self.rolling_dir / "periods.json"
        self.history_file = self.rolling_dir / "history.json"
        
        self._save_config()
        self.periods: List[RollingPeriod] = self._load_periods()
    
    def _save_config(self):
        """保存滚动训练配置"""
        config = {
            "window_size": self.window_size,
            "step_size": self.step_size,
            "valid_size": self.valid_size,
            "test_size": self.test_size,
            "mode": self.mode,
            "min_periods": self.min_periods,
            "created_at": datetime.now().isoformat(),
        }
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Rolling config saved to {self.config_file}")
    
    def _load_periods(self) -> List[RollingPeriod]:
        """加载已保存的周期信息"""
        if self.periods_file.exists():
            with open(self.periods_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [RollingPeriod(**p) for p in data]
        return []
    
    def _save_periods(self):
        """保存周期信息"""
        with open(self.periods_file, "w", encoding="utf-8") as f:
            json.dump([p.__dict__ for p in self.periods], f, indent=2, ensure_ascii=False)
    
    def generate_periods(
        self,
        calendar_start: str,
        calendar_end: str,
        force: bool = False
    ) -> List[RollingPeriod]:
        """
        生成滚动训练时间段
        
        Args:
            calendar_start: 日历开始日期 (YYYY-MM-DD)
            calendar_end: 日历结束日期 (YYYY-MM-DD)
            force: 是否重新生成（忽略已存在的周期）
            
        Returns:
            生成的滚动周期列表
        """
        logger.info(f"Generating rolling periods from {calendar_start} to {calendar_end}")
        logger.info(f"Mode: {self.mode}, Window: {self.window_size}d, Step: {self.step_size}d")
        
        # 获取交易日历（简化版，实际应从 Qlib 获取）
        calendar = pd.date_range(
            start=calendar_start,
            end=calendar_end,
            freq='B'  # 工作日
        )
        total_days = len(calendar)
        logger.info(f"Total trading days: {total_days}")
        
        if force:
            self.periods = []
        
        if self.mode == "rolling":
            periods = self._generate_rolling_periods(calendar)
        else:  # expanding
            periods = self._generate_expanding_periods(calendar)
        
        # 添加新周期
        existing_ids = {p.period_id for p in self.periods}
        new_periods = [p for p in periods if p.period_id not in existing_ids]
        
        self.periods.extend(new_periods)
        self._save_periods()
        
        logger.info(f"Generated {len(new_periods)} new periods, total: {len(self.periods)}")
        return new_periods
    
    def _generate_rolling_periods(self, calendar: pd.DatetimeIndex) -> List[RollingPeriod]:
        """生成固定窗口滚动周期"""
        periods = []
        n = len(calendar)
        
        # 需要的最小天数
        min_days = self.window_size + self.valid_size + self.test_size
        
        if n < min_days:
            logger.warning(f"Not enough data: {n} < {min_days}")
            return periods
        
        # 从后往前推，确保最后一个周期包含最新数据
        current_end_idx = n - 1
        
        while True:
            # 计算各段边界
            test_start_idx = current_end_idx - self.test_size + 1
            valid_start_idx = test_start_idx - self.valid_size
            train_start_idx = valid_start_idx - self.window_size + 1
            
            if train_start_idx < 0:
                break
            
            period_id = f"roll_{calendar[current_end_idx].strftime('%Y%m%d')}"
            
            period = RollingPeriod(
                period_id=period_id,
                train_start=calendar[train_start_idx].strftime("%Y-%m-%d"),
                train_end=calendar[valid_start_idx - 1].strftime("%Y-%m-%d"),
                valid_start=calendar[valid_start_idx].strftime("%Y-%m-%d"),
                valid_end=calendar[test_start_idx - 1].strftime("%Y-%m-%d"),
                test_start=calendar[test_start_idx].strftime("%Y-%m-%d"),
                test_end=calendar[current_end_idx].strftime("%Y-%m-%d"),
            )
            periods.append(period)
            
            # 向前滚动
            current_end_idx -= self.step_size
            
            if current_end_idx < min_days - 1:
                break
        
        # 反转顺序，从早到晚
        periods.reverse()
        return periods
    
    def _generate_expanding_periods(self, calendar: pd.DatetimeIndex) -> List[RollingPeriod]:
        """生成扩展窗口周期"""
        periods = []
        n = len(calendar)
        
        # 初始训练窗口
        min_train_days = self.window_size
        min_total_days = min_train_days + self.valid_size + self.test_size
        
        if n < min_total_days:
            logger.warning(f"Not enough data: {n} < {min_total_days}")
            return periods
        
        # 固定训练起点
        train_start_idx = 0
        current_end_idx = min_train_days - 1
        
        while True:
            # 计算各段边界
            test_start_idx = current_end_idx + 1
            valid_start_idx = test_start_idx
            test_end_idx = test_start_idx + self.test_size - 1
            
            if test_end_idx >= n:
                break
            
            # 验证集在测试集之前
            valid_start_idx = max(train_start_idx, test_start_idx - self.valid_size)
            
            period_id = f"exp_{calendar[test_end_idx].strftime('%Y%m%d')}"
            
            period = RollingPeriod(
                period_id=period_id,
                train_start=calendar[train_start_idx].strftime("%Y-%m-%d"),
                train_end=calendar[valid_start_idx - 1].strftime("%Y-%m-%d"),
                valid_start=calendar[valid_start_idx].strftime("%Y-%m-%d"),
                valid_end=calendar[test_start_idx - 1].strftime("%Y-%m-%d"),
                test_start=calendar[test_start_idx].strftime("%Y-%m-%d"),
                test_end=calendar[test_end_idx].strftime("%Y-%m-%d"),
            )
            periods.append(period)
            
            # 扩展窗口
            current_end_idx += self.step_size
        
        return periods
    
    def train_all_periods(
        self,
        base_config: Dict[str, Any],
        max_workers: int = 1,
        skip_completed: bool = True
    ) -> Dict[str, Any]:
        """
        训练所有滚动周期
        
        Args:
            base_config: 基础训练配置
            max_workers: 并行工作进程数（当前仅支持串行）
            skip_completed: 跳过已完成的周期
            
        Returns:
            训练结果汇总
        """
        logger.info(f"Starting training for {len(self.periods)} periods")
        
        results = {
            "total": len(self.periods),
            "completed": 0,
            "failed": 0,
            "skipped": 0,
            "metrics_summary": {},
        }
        
        all_metrics = []
        
        for period in self.periods:
            if skip_completed and period.status == "completed":
                logger.info(f"Skipping completed period: {period.period_id}")
                results["skipped"] += 1
                if period.metrics:
                    all_metrics.append(period.metrics)
                continue
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Training period: {period.period_id}")
            logger.info(f"Train: {period.train_start} ~ {period.train_end}")
            logger.info(f"Valid: {period.valid_start} ~ {period.valid_end}")
            logger.info(f"Test:  {period.test_start} ~ {period.test_end}")
            logger.info(f"{'='*60}\n")
            
            try:
                # 更新状态
                period.status = "running"
                self._save_periods()
                
                # 创建周期目录
                period_dir = self.rolling_dir / period.period_id
                period_dir.mkdir(exist_ok=True)
                
                # 生成该周期的配置文件
                period_config = self._prepare_period_config(base_config, period)
                config_path = period_dir / "config.yaml"
                with open(config_path, "w", encoding="utf-8") as f:
                    yaml.dump(period_config, f, default_flow_style=False, allow_unicode=True)
                
                # 执行训练
                log_path = period_dir / "train.log"
                result = subprocess.run(
                    ["qrun", str(config_path)],
                    capture_output=True,
                    text=True,
                    cwd=str(period_dir),
                    timeout=7200,  # 2 小时超时
                )
                
                # 保存日志
                with open(log_path, "w", encoding="utf-8") as f:
                    f.write(result.stdout)
                    f.write(result.stderr)
                
                if result.returncode == 0:
                    period.status = "completed"
                    period.model_path = str(period_dir / "trained_model.pkl")
                    
                    # 尝试读取指标
                    metrics = self._extract_metrics(period_dir)
                    period.metrics = metrics
                    all_metrics.append(metrics)
                    
                    logger.info(f"✓ Period {period.period_id} completed successfully")
                    results["completed"] += 1
                else:
                    period.status = "failed"
                    logger.error(f"✗ Period {period.period_id} failed: {result.stderr[:500]}")
                    results["failed"] += 1
                
            except subprocess.TimeoutExpired:
                period.status = "failed"
                logger.error(f"✗ Period {period.period_id} timed out")
                results["failed"] += 1
                
            except Exception as e:
                period.status = "failed"
                logger.error(f"✗ Period {period.period_id} error: {str(e)}")
                results["failed"] += 1
            
            finally:
                self._save_periods()
        
        # 计算指标汇总
        if all_metrics:
            results["metrics_summary"] = self._aggregate_metrics(all_metrics)
        
        # 保存历史
        self._save_history(results)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Rolling training finished!")
        logger.info(f"Completed: {results['completed']}, Failed: {results['failed']}, Skipped: {results['skipped']}")
        logger.info(f"{'='*60}\n")
        
        return results
    
    def _prepare_period_config(
        self,
        base_config: Dict[str, Any],
        period: RollingPeriod
    ) -> Dict[str, Any]:
        """为特定周期准备配置"""
        import copy
        config = copy.deepcopy(base_config)
        
        # 更新数据时间段
        if "data_handler" in config:
            config["data_handler"]["start_time"] = period.train_start
            config["data_handler"]["end_time"] = period.test_end
            config["data_handler"]["fit_start_time"] = period.train_start
            config["data_handler"]["fit_end_time"] = period.train_end
        
        if "dataset" in config and "segments" in config["dataset"]:
            config["dataset"]["segments"] = {
                "train": [period.train_start, period.train_end],
                "valid": [period.valid_start, period.valid_end],
                "test": [period.test_start, period.test_end],
            }
        
        if "backtest" in config:
            config["backtest"]["start_time"] = period.test_start
            config["backtest"]["end_time"] = period.test_end
        
        return config
    
    def _extract_metrics(self, period_dir: Path) -> Dict[str, float]:
        """从训练结果中提取指标"""
        metrics = {}
        
        # 尝试从多个位置读取指标
        possible_files = [
            period_dir / "metrics.json",
            period_dir / "result.json",
            period_dir / "portfolio_analysis.json",
        ]
        
        for file_path in possible_files:
            if file_path.exists():
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        # 提取常见指标
                        for key in ["ic", "rank_ic", "information_ratio", 
                                   "annualized_return", "max_drawdown", "sharpe"]:
                            if key in data:
                                metrics[key] = float(data[key])
                            elif isinstance(data, dict):
                                # 嵌套查找
                                for k, v in data.items():
                                    if key in k.lower() and isinstance(v, (int, float)):
                                        metrics[k] = float(v)
                except Exception as e:
                    logger.warning(f"Failed to read metrics from {file_path}: {e}")
        
        # 如果没找到指标文件，尝试从日志解析
        log_file = period_dir / "train.log"
        if log_file.exists() and not metrics:
            metrics = self._parse_metrics_from_log(log_file)
        
        return metrics
    
    def _parse_metrics_from_log(self, log_path: Path) -> Dict[str, float]:
        """从日志文件中解析指标（简化版）"""
        metrics = {}
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
                # 简单正则匹配（可根据实际日志格式调整）
                import re
                patterns = {
                    "ic": r"IC\s*[:=]\s*([\d.]+)",
                    "rank_ic": r"Rank IC\s*[:=]\s*([\d.]+)",
                    "information_ratio": r"IR\s*[:=]\s*([\d.]+)",
                    "sharpe": r"Sharpe\s*[:=]\s*([\d.]+)",
                }
                for name, pattern in patterns.items():
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        metrics[name] = float(match.group(1))
        except Exception as e:
            logger.warning(f"Failed to parse log: {e}")
        return metrics
    
    def _aggregate_metrics(self, all_metrics: List[Dict[str, float]]) -> Dict[str, Any]:
        """聚合多个周期的指标"""
        if not all_metrics:
            return {}
        
        # 转为 DataFrame
        df = pd.DataFrame(all_metrics)
        
        summary = {}
        for col in df.columns:
            summary[f"{col}_mean"] = round(df[col].mean(), 6)
            summary[f"{col}_std"] = round(df[col].std(), 6)
            summary[f"{col}_min"] = round(df[col].min(), 6)
            summary[f"{col}_max"] = round(df[col].max(), 6)
        
        # 稳定性指标
        if "ic" in df.columns:
            summary["ic_stability"] = round(df["ic"].mean() / (df["ic"].std() + 1e-9), 4)
        
        return summary
    
    def _save_history(self, results: Dict[str, Any]):
        """保存训练历史"""
        history = {
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "periods": [p.__dict__ for p in self.periods],
        }
        
        # 追加到历史文件
        histories = []
        if self.history_file.exists():
            with open(self.history_file, "r", encoding="utf-8") as f:
                histories = json.load(f)
        
        histories.append(history)
        
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(histories, f, indent=2, ensure_ascii=False)
    
    def get_latest_model(self) -> Optional[Path]:
        """获取最新的模型路径"""
        completed_periods = [p for p in self.periods if p.status == "completed" and p.model_path]
        if not completed_periods:
            return None
        
        # 按 period_id 排序（最新的在后）
        completed_periods.sort(key=lambda p: p.period_id)
        latest = completed_periods[-1]
        
        return Path(latest.model_path)
    
    def get_best_model(self, metric: str = "ic") -> Optional[Path]:
        """获取指定指标最优的模型路径"""
        completed_periods = [
            p for p in self.periods 
            if p.status == "completed" and p.model_path and metric in p.metrics
        ]
        
        if not completed_periods:
            return None
        
        # 找出指标最优的
        best_period = max(completed_periods, key=lambda p: p.metrics[metric])
        logger.info(f"Best model by {metric}: {best_period.period_id} ({best_period.metrics[metric]})")
        
        return Path(best_period.model_path)
    
    def export_ensemble_config(self, output_path: str, top_k: int = 5):
        """导出 Ensemble 配置（选取 top K 模型）"""
        completed_periods = [
            p for p in self.periods 
            if p.status == "completed" and p.model_path and "ic" in p.metrics
        ]
        
        if not completed_periods:
            logger.warning("No completed periods found")
            return
        
        # 按 IC 排序取 top K
        completed_periods.sort(key=lambda p: p.metrics.get("ic", 0), reverse=True)
        top_periods = completed_periods[:top_k]
        
        ensemble_config = {
            "models": [
                {
                    "period_id": p.period_id,
                    "model_path": p.model_path,
                    "ic": p.metrics.get("ic"),
                    "weight": 1.0 / top_k  # 等权重
                }
                for p in top_periods
            ],
            "ensemble_method": "average",
            "created_at": datetime.now().isoformat(),
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ensemble_config, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Ensemble config exported to {output_path}")
        return ensemble_config


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Rolling Training Engine")
    parser.add_argument("--experiment-dir", type=str, required=True, help="实验目录")
    parser.add_argument("--window-size", type=int, default=252*3, help="训练窗口大小（天）")
    parser.add_argument("--step-size", type=int, default=252, help="滚动步长（天）")
    parser.add_argument("--mode", type=str, default="rolling", choices=["rolling", "expanding"])
    parser.add_argument("--calendar-start", type=str, required=True, help="日历开始日期")
    parser.add_argument("--calendar-end", type=str, required=True, help="日历结束日期")
    parser.add_argument("--config", type=str, required=True, help="基础配置文件路径")
    parser.add_argument("--force", action="store_true", help="重新生成周期")
    
    args = parser.parse_args()
    
    # 加载基础配置
    with open(args.config, "r", encoding="utf-8") as f:
        base_config = yaml.safe_load(f)
    
    # 创建训练器
    trainer = RollingTrainer(
        experiment_dir=args.experiment_dir,
        window_size=args.window_size,
        step_size=args.step_size,
        mode=args.mode,
    )
    
    # 生成周期
    trainer.generate_periods(args.calendar_start, args.calendar_end, force=args.force)
    
    # 开始训练
    results = trainer.train_all_periods(base_config)
    
    print("\n" + "="*60)
    print("ROLLING TRAINING SUMMARY")
    print("="*60)
    print(f"Total periods: {results['total']}")
    print(f"Completed: {results['completed']}")
    print(f"Failed: {results['failed']}")
    print(f"Skipped: {results['skipped']}")
    if results['metrics_summary']:
        print("\nMetrics Summary:")
        for k, v in results['metrics_summary'].items():
            print(f"  {k}: {v}")
    print("="*60)
