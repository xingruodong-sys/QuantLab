"""
Task Scheduler - 定时任务调度器
使用 APScheduler 实现训练和预测任务的定时调度
支持 Cron 表达式配置
"""

import os
import sys
import json
import yaml
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, Callable
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import pandas as pd

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class TaskScheduler:
    """
    任务调度器
    
    支持的任务类型：
    1. rolling_train: 滚动训练任务
    2. daily_predict: 每日预测任务
    3. data_update: 数据更新任务
    4. custom: 自定义任务
    
    调度方式：
    1. Cron: 基于 cron 表达式
    2. Interval: 固定时间间隔
    3. Date: 一次性执行
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        scheduler_type: str = "background",  # background/blocking
        timezone: str = "Asia/Shanghai"
    ):
        """
        Args:
            config_path: 配置文件路径
            scheduler_type: 调度器类型
            timezone: 时区
        """
        self.config_path = Path(config_path) if config_path else None
        self.config = self._load_config()
        self.timezone = timezone
        
        # 初始化调度器
        if scheduler_type == "blocking":
            self.scheduler = BlockingScheduler(timezone=timezone)
        else:
            self.scheduler = BackgroundScheduler(timezone=timezone)
        
        # 任务注册表
        self.task_registry: Dict[str, Dict] = {}
        
        # 任务历史
        self.history_file = Path("./scheduler_history.json")
        self.task_history = self._load_history()
        
        # 绑定事件监听
        self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
        
        logger.info(f"TaskScheduler initialized with {scheduler_type} scheduler")
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if self.config_path and self.config_path.exists():
            with open(self.config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        
        # 返回默认配置
        return self._default_config()
    
    def _default_config(self) -> Dict:
        """默认调度配置"""
        return {
            "rolling_train": {
                "enabled": True,
                "cron": "0 20 * * 5",  # 每周五晚上 8 点
                "params": {
                    "window_size": 252 * 3,
                    "step_size": 252,
                    "mode": "rolling"
                }
            },
            "daily_predict": {
                "enabled": True,
                "cron": "0 9 * * 1-5",  # 交易日早上 9 点
                "params": {
                    "top_k": 50,
                    "n_drop": 5,
                    "universe": "csi300"
                }
            },
            "data_update": {
                "enabled": True,
                "cron": "0 18 * * *",  # 每天下午 6 点
                "params": {}
            }
        }
    
    def _load_history(self) -> list:
        """加载任务历史"""
        if self.history_file.exists():
            with open(self.history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return []
    
    def _save_history(self):
        """保存任务历史"""
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.task_history, f, indent=2, ensure_ascii=False)
    
    def _on_job_executed(self, event):
        """任务执行成功回调"""
        job_id = event.job_id
        logger.info(f"Job executed successfully: {job_id}")
        
        self.task_history.append({
            "job_id": job_id,
            "status": "success",
            "executed_at": datetime.now().isoformat(),
            "message": "Job completed"
        })
        self._save_history()
    
    def _on_job_error(self, event):
        """任务执行失败回调"""
        job_id = event.job_id
        exception = event.exception
        
        logger.error(f"Job execution failed: {job_id}, error: {exception}")
        
        self.task_history.append({
            "job_id": job_id,
            "status": "failed",
            "executed_at": datetime.now().isoformat(),
            "error": str(exception)
        })
        self._save_history()
    
    def register_task(
        self,
        task_id: str,
        task_func: Callable,
        trigger_type: str = "cron",
        trigger_params: Optional[Dict] = None,
        task_params: Optional[Dict] = None,
        enabled: bool = True
    ):
        """
        注册定时任务
        
        Args:
            task_id: 任务 ID
            task_func: 任务函数
            trigger_type: 触发器类型 (cron/interval/date)
            trigger_params: 触发器参数
            task_params: 任务执行参数
            enabled: 是否启用
        """
        if not enabled:
            logger.info(f"Task {task_id} is disabled, skipping registration")
            return
        
        # 构建触发器
        if trigger_type == "cron":
            cron_expr = trigger_params.get("cron", "0 0 * * *")
            parts = cron_expr.split()
            
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
            elif len(parts) == 6:
                second, minute, hour, day, month, day_of_week = parts
                trigger_params["second"] = second
            
            trigger = CronTrigger(
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                timezone=self.timezone
            )
            
        elif trigger_type == "interval":
            trigger = IntervalTrigger(
                seconds=trigger_params.get("seconds"),
                minutes=trigger_params.get("minutes"),
                hours=trigger_params.get("hours"),
                days=trigger_params.get("days"),
                timezone=self.timezone
            )
            
        elif trigger_type == "date":
            run_date = trigger_params.get("run_date")
            if isinstance(run_date, str):
                run_date = datetime.fromisoformat(run_date)
            trigger = DateTrigger(run_date=run_date)
        
        else:
            raise ValueError(f"Unknown trigger type: {trigger_type}")
        
        # 添加任务到调度器
        job = self.scheduler.add_job(
            func=task_func,
            trigger=trigger,
            id=task_id,
            name=task_id,
            kwargs=task_params or {},
            replace_existing=True,
            misfire_grace_time=3600,  # 1 小时容错时间
            coalesce=True  # 合并错过的执行
        )
        
        # 记录注册信息
        self.task_registry[task_id] = {
            "task_id": task_id,
            "function": task_func.__name__,
            "trigger_type": trigger_type,
            "trigger_params": trigger_params,
            "task_params": task_params,
            "enabled": enabled,
            "registered_at": datetime.now().isoformat(),
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None
        }
        
        logger.info(f"Task registered: {task_id}, next run: {job.next_run_time}")
        
        return job
    
    def register_rolling_train(
        self,
        experiment_dir: str,
        config_path: str,
        calendar_start: str,
        calendar_end: str
    ):
        """注册滚动训练任务"""
        from rolling_trainer import RollingTrainer
        
        def run_rolling_train():
            logger.info("="*60)
            logger.info("Starting Rolling Training Task")
            logger.info("="*60)
            
            try:
                # 加载配置
                with open(config_path, "r", encoding="utf-8") as f:
                    base_config = yaml.safe_load(f)
                
                # 创建训练器
                trainer = RollingTrainer(
                    experiment_dir=experiment_dir,
                    window_size=self.config.get("rolling_train", {}).get("params", {}).get("window_size", 252*3),
                    step_size=self.config.get("rolling_train", {}).get("params", {}).get("step_size", 252),
                    mode=self.config.get("rolling_train", {}).get("params", {}).get("mode", "rolling")
                )
                
                # 生成周期并训练
                trainer.generate_periods(calendar_start, calendar_end)
                results = trainer.train_all_periods(base_config)
                
                logger.info(f"Rolling training completed: {results}")
                
            except Exception as e:
                logger.error(f"Rolling training failed: {e}", exc_info=True)
                raise
        
        cron_config = self.config.get("rolling_train", {})
        self.register_task(
            task_id="rolling_train",
            task_func=run_rolling_train,
            trigger_type="cron",
            trigger_params={"cron": cron_config.get("cron", "0 20 * * 5")},
            enabled=cron_config.get("enabled", True)
        )
    
    def register_daily_predict(
        self,
        model_dir: str,
        output_dir: str,
        universe: str = "csi300",
        top_k: int = 50
    ):
        """注册每日预测任务"""
        from daily_prediction import DailyPredictor
        
        def run_daily_predict():
            logger.info("="*60)
            logger.info("Starting Daily Prediction Task")
            logger.info("="*60)
            
            try:
                # 创建预测器
                predictor = DailyPredictor(
                    model_dir=model_dir,
                    output_dir=Path(output_dir)
                )
                
                # 运行流水线
                results = predictor.run_full_pipeline(
                    date=None,  # 自动使用最近交易日
                    universe=universe,
                    top_k=top_k,
                    n_drop=self.config.get("daily_predict", {}).get("params", {}).get("n_drop", 5)
                )
                
                logger.info(f"Daily prediction completed: {results['status']}")
                
            except Exception as e:
                logger.error(f"Daily prediction failed: {e}", exc_info=True)
                raise
        
        cron_config = self.config.get("daily_predict", {})
        predict_params = cron_config.get("params", {})
        
        self.register_task(
            task_id="daily_predict",
            task_func=run_daily_predict,
            trigger_type="cron",
            trigger_params={"cron": cron_config.get("cron", "0 9 * * 1-5")},
            task_params={
                "universe": predict_params.get("universe", universe),
                "top_k": predict_params.get("top_k", top_k)
            },
            enabled=cron_config.get("enabled", True)
        )
    
    def register_data_update(self, update_func: Callable):
        """注册数据更新任务"""
        cron_config = self.config.get("data_update", {})
        
        self.register_task(
            task_id="data_update",
            task_func=update_func,
            trigger_type="cron",
            trigger_params={"cron": cron_config.get("cron", "0 18 * * *")},
            enabled=cron_config.get("enabled", True)
        )
    
    def start(self, blocking: bool = True):
        """
        启动调度器
        
        Args:
            blocking: 是否阻塞运行
        """
        logger.info("Starting scheduler...")
        logger.info(f"Registered tasks: {list(self.task_registry.keys())}")
        
        # 打印下次执行时间
        for job in self.scheduler.get_jobs():
            logger.info(f"  - {job.id}: next run at {job.next_run_time}")
        
        try:
            self.scheduler.start(blocking=blocking)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
    
    def stop(self):
        """停止调度器"""
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")
    
    def pause_task(self, task_id: str):
        """暂停任务"""
        try:
            self.scheduler.pause_job(task_id)
            logger.info(f"Task paused: {task_id}")
        except Exception as e:
            logger.error(f"Failed to pause task: {e}")
    
    def resume_task(self, task_id: str):
        """恢复任务"""
        try:
            self.scheduler.resume_job(task_id)
            logger.info(f"Task resumed: {task_id}")
        except Exception as e:
            logger.error(f"Failed to resume task: {e}")
    
    def remove_task(self, task_id: str):
        """移除任务"""
        try:
            self.scheduler.remove_job(task_id)
            del self.task_registry[task_id]
            logger.info(f"Task removed: {task_id}")
        except Exception as e:
            logger.error(f"Failed to remove task: {e}")
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        job = self.scheduler.get_job(task_id)
        if job:
            return {
                "task_id": task_id,
                "enabled": True,
                "paused": job.paused,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "registry": self.task_registry.get(task_id)
            }
        return None
    
    def get_all_status(self) -> Dict:
        """获取所有任务状态"""
        status = {
            "running": self.scheduler.running,
            "tasks": {}
        }
        
        for job in self.scheduler.get_jobs():
            status["tasks"][job.id] = {
                "enabled": True,
                "paused": job.paused,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None
            }
        
        # 添加禁用的任务
        for task_id, info in self.task_registry.items():
            if task_id not in status["tasks"]:
                status["tasks"][task_id] = {
                    "enabled": False,
                    "info": info
                }
        
        return status
    
    def run_now(self, task_id: str):
        """立即执行任务"""
        job = self.scheduler.get_job(task_id)
        if job:
            logger.info(f"Manually triggering task: {task_id}")
            job.modify(next_run_time=datetime.now())
        else:
            logger.warning(f"Task not found: {task_id}")


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Task Scheduler")
    parser.add_argument("--config", type=str, default="./scheduler_config.yaml", help="配置文件")
    parser.add_argument("--experiment-dir", type=str, default="./experiments", help="实验目录")
    parser.add_argument("--model-dir", type=str, default="./experiments", help="模型目录")
    parser.add_argument("--output-dir", type=str, default="./predictions", help="输出目录")
    parser.add_argument("--action", type=str, default="start", choices=["start", "status", "run"])
    parser.add_argument("--task", type=str, default=None, help="指定任务 ID")
    
    args = parser.parse_args()
    
    # 创建调度器
    scheduler = TaskScheduler(config_path=args.config)
    
    # 注册默认任务
    scheduler.register_rolling_train(
        experiment_dir=args.experiment_dir,
        config_path=args.config,
        calendar_start="2018-01-01",
        calendar_end="2024-12-31"
    )
    
    scheduler.register_daily_predict(
        model_dir=args.model_dir,
        output_dir=args.output_dir
    )
    
    if args.action == "start":
        scheduler.start(blocking=True)
    
    elif args.action == "status":
        status = scheduler.get_all_status()
        print(json.dumps(status, indent=2))
    
    elif args.action == "run" and args.task:
        scheduler.run_now(args.task)
