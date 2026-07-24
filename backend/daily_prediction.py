"""
Daily Prediction Pipeline - 每日预测流水线
用于生产环境的实时预测和信号生成
支持：
- 实时数据获取（AKShare/Tushare）
- 特征工程实时更新
- 模型推理
- 交易信号生成与存储
"""

import os
import sys
import json
import pickle
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Any
import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class DailyPredictor:
    """
    每日预测引擎
    
    工作流程：
    1. 加载最新模型
    2. 获取最新行情数据
    3. 计算特征因子
    4. 模型推理生成预测
    5. 生成交易信号
    6. 保存信号到数据库/文件
    """
    
    def __init__(
        self,
        model_dir: Path,
        data_provider: str = "akshare",  # akshare/tushare/qlib
        feature_config: Optional[Dict] = None,
        output_dir: Optional[Path] = None
    ):
        """
        Args:
            model_dir: 模型目录路径
            data_provider: 数据源提供商
            feature_config: 特征配置
            output_dir: 输出目录
        """
        self.model_dir = Path(model_dir)
        self.data_provider = data_provider
        self.feature_config = feature_config or self._default_feature_config()
        self.output_dir = output_dir or Path("./predictions")
        
        self.output_dir.mkdir(exist_ok=True)
        
        # 缓存
        self._model_cache = {}
        self._data_cache = {}
        
        logger.info(f"DailyPredictor initialized with {data_provider} provider")
    
    def _default_feature_config(self) -> Dict:
        """默认特征配置"""
        return {
            "features": [
                "ret_1d", "ret_5d", "ret_10d", "ret_20d",
                "vol_5d_avg", "vol_20d_avg",
                "rsi_14", "macd", "bollinger_position",
                "turnover_rate", "pe_ttm", "pb"
            ],
            "label": "ret_5d",  # 预测 5 日收益
            "lookback_window": 60,  # 计算特征所需的历史窗口
        }
    
    def load_model(self, model_path: Optional[str] = None, exp_id: Optional[str] = None) -> Any:
        """
        加载预测模型
        
        Args:
            model_path: 模型文件路径（可选，如不传则自动查找最新）
            exp_id: 实验 ID（可选）
            
        Returns:
            加载的模型对象
        """
        if model_path in self._model_cache:
            logger.info(f"Loading model from cache: {model_path}")
            return self._model_cache[model_path]
        
        # 自动查找模型
        if not model_path:
            if exp_id:
                # 从指定实验目录查找
                model_file = self.model_dir / exp_id / "trained_model.pkl"
            else:
                # 查找最新的模型
                model_file = self._find_latest_model()
            
            if not model_file or not Path(model_file).exists():
                raise FileNotFoundError("No model found. Please specify model_path or train a model first.")
            
            model_path = str(model_file)
        
        logger.info(f"Loading model from: {model_path}")
        
        try:
            with open(model_path, "rb") as f:
                model = pickle.load(f)
            
            self._model_cache[model_path] = model
            logger.info(f"Model loaded successfully: {model_path}")
            return model
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _find_latest_model(self) -> Optional[Path]:
        """查找最新的模型文件"""
        model_files = list(self.model_dir.glob("**/trained_model.pkl"))
        
        if not model_files:
            return None
        
        # 按修改时间排序
        model_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return model_files[0]
    
    def fetch_latest_data(
        self,
        date: Optional[str] = None,
        universe: str = "csi300"
    ) -> pd.DataFrame:
        """
        获取最新行情数据
        
        Args:
            date: 交易日期（YYYY-MM-DD），默认为最近交易日
            universe: 股票池 (csi300/csi500/all)
            
        Returns:
            包含行情数据的 DataFrame
        """
        if date is None:
            # 获取最近交易日（简化：取昨天）
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        cache_key = f"{date}_{universe}"
        if cache_key in self._data_cache:
            logger.info(f"Using cached data for {cache_key}")
            return self._data_cache[cache_key]
        
        logger.info(f"Fetching data for {date}, universe: {universe}")
        
        # 根据数据源获取数据
        if self.data_provider == "akshare":
            df = self._fetch_akshare_data(date, universe)
        elif self.data_provider == "tushare":
            df = self._fetch_tushare_data(date, universe)
        elif self.data_provider == "qlib":
            df = self._fetch_qlib_data(date, universe)
        else:
            raise ValueError(f"Unknown data provider: {self.data_provider}")
        
        if df is not None:
            self._data_cache[cache_key] = df
            logger.info(f"Fetched {len(df)} stocks data")
        
        return df
    
    def _fetch_akshare_data(self, date: str, universe: str) -> pd.DataFrame:
        """从 AKShare 获取数据"""
        try:
            import akshare as ak
            
            # 获取股票列表
            if universe == "csi300":
                # 沪深 300 成分股（简化实现）
                stock_list = self._get_csi300_stocks()
            elif universe == "csi500":
                stock_list = self._get_csi500_stocks()
            else:
                # 全市场（简化：取部分活跃股）
                stock_list = self._get_all_stocks()[:500]
            
            # 获取历史行情
            all_data = []
            for symbol in stock_list[:50]:  # 限制数量避免超时
                try:
                    df = ak.stock_zh_a_hist(
                        symbol=symbol,
                        period="daily",
                        start_date=(datetime.strptime(date, "%Y-%m-%d") - timedelta(days=60)).strftime("%Y%m%d"),
                        end_date=date.replace("-", ""),
                        adjust="qfq"
                    )
                    if len(df) > 0:
                        df["symbol"] = symbol
                        all_data.append(df)
                except Exception as e:
                    logger.warning(f"Failed to fetch {symbol}: {e}")
                    continue
            
            if all_data:
                return pd.concat(all_data, ignore_index=True)
            else:
                logger.warning("No data fetched from AKShare")
                return pd.DataFrame()
                
        except ImportError:
            logger.error("AKShare not installed. Run: pip install akshare")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching AKShare data: {e}")
            return pd.DataFrame()
    
    def _fetch_tushare_data(self, date: str, universe: str) -> pd.DataFrame:
        """从 Tushare 获取数据"""
        try:
            import tushare as ts
            
            # 需要配置 token
            token = os.getenv("TUSHARE_TOKEN", "")
            if not token:
                logger.warning("TUSHARE_TOKEN not set")
                return pd.DataFrame()
            
            ts.set_token(token)
            pro = ts.pro_api()
            
            # 获取日线数据
            df = pro.daily(
                trade_date=date.replace("-", ""),
                start_date=(datetime.strptime(date, "%Y-%m-%d") - timedelta(days=60)).strftime("%Y%m%d")
            )
            
            return df
            
        except ImportError:
            logger.error("Tushare not installed. Run: pip install tushare")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching Tushare data: {e}")
            return pd.DataFrame()
    
    def _fetch_qlib_data(self, date: str, universe: str) -> pd.DataFrame:
        """从 Qlib 获取数据"""
        try:
            import qlib
            from qlib.data import D
            
            # 初始化 Qlib（如果尚未初始化）
            if not hasattr(qlib, 'Q'):
                qlib.init(provider_uri="~/.qlib/qlib_data/cn_data")
            
            # 获取股票池
            if universe == "csi300":
                instruments = D.instruments("csi300")
            else:
                instruments = D.instruments("all")
            
            # 获取行情数据
            df = D.features(
                instruments,
                ["$close", "$open", "$high", "$low", "$volume", "$factor"],
                start_time=(datetime.strptime(date, "%Y-%m-%d") - timedelta(days=60)).strftime("%Y-%m-%d"),
                end_time=date
            )
            
            return df.reset_index()
            
        except Exception as e:
            logger.error(f"Error fetching Qlib data: {e}")
            return pd.DataFrame()
    
    def _get_csi300_stocks(self) -> List[str]:
        """获取沪深 300 成分股（简化版）"""
        # 实际应从指数成分股接口获取
        return [
            "000001", "000002", "000063", "000100", "000157",
            "000333", "000538", "000568", "000596", "000625",
            "000651", "000661", "000725", "000776", "000858",
            "000895", "002001", "002007", "002027", "002049",
            "600000", "600009", "600016", "600028", "600030",
            "600031", "600036", "600048", "600050", "600104",
        ]
    
    def _get_csi500_stocks(self) -> List[str]:
        """获取中证 500 成分股（简化版）"""
        return self._get_csi300_stocks()  # 简化处理
    
    def _get_all_stocks(self) -> List[str]:
        """获取全市场股票（简化版）"""
        return self._get_csi300_stocks() * 3  # 简化处理
    
    def calculate_features(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        计算特征因子
        
        Args:
            price_data: 原始行情数据
            
        Returns:
            包含特征的数据集
        """
        logger.info("Calculating features...")
        
        if price_data.empty:
            return pd.DataFrame()
        
        # 确保有 symbol 列
        if "symbol" not in price_data.columns and "instrument" in price_data.columns:
            price_data["symbol"] = price_data["instrument"]
        
        # 按股票分组计算特征
        feature_dfs = []
        
        for symbol in price_data["symbol"].unique():
            stock_df = price_data[price_data["symbol"] == symbol].copy()
            
            if len(stock_df) < 20:
                continue
            
            # 按日期排序
            if "date" in stock_df.columns:
                stock_df = stock_df.sort_values("date")
            elif "datetime" in stock_df.columns:
                stock_df = stock_df.sort_values("datetime")
            else:
                stock_df = stock_df.sort_index()
            
            # 计算基础特征
            try:
                # 收益率
                stock_df["ret_1d"] = stock_df["close"].pct_change(1)
                stock_df["ret_5d"] = stock_df["close"].pct_change(5)
                stock_df["ret_10d"] = stock_df["close"].pct_change(10)
                stock_df["ret_20d"] = stock_df["close"].pct_change(20)
                
                # 成交量均线
                if "volume" in stock_df.columns:
                    stock_df["vol_5d_avg"] = stock_df["volume"].rolling(5).mean()
                    stock_df["vol_20d_avg"] = stock_df["volume"].rolling(20).mean()
                
                # RSI
                stock_df["rsi_14"] = self._calculate_rsi(stock_df["close"], 14)
                
                # MACD
                macd = self._calculate_macd(stock_df["close"])
                stock_df["macd"] = macd["macd"]
                
                # 布林带位置
                boll = self._calculate_bollinger(stock_df["close"])
                stock_df["bollinger_position"] = boll["position"]
                
                # 添加股票标识
                stock_df["symbol"] = symbol
                
                feature_dfs.append(stock_df)
                
            except Exception as e:
                logger.warning(f"Error calculating features for {symbol}: {e}")
                continue
        
        if feature_dfs:
            result = pd.concat(feature_dfs, ignore_index=True)
            # 只保留最后一天的数据（最新）
            if "date" in result.columns:
                latest_date = result["date"].max()
                result = result[result["date"] == latest_date]
            elif "datetime" in result.columns:
                latest_date = result["datetime"].max()
                result = result[result["datetime"] == latest_date]
            
            logger.info(f"Features calculated for {result['symbol'].nunique()} stocks")
            return result
        else:
            return pd.DataFrame()
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """计算 RSI 指标"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-9)
        return 100 - (100 / (1 + rs))
    
    def _calculate_macd(self, prices: pd.Series) -> Dict[str, pd.Series]:
        """计算 MACD 指标"""
        exp1 = prices.ewm(span=12, adjust=False).mean()
        exp2 = prices.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return {"macd": macd, "signal": signal, "hist": hist}
    
    def _calculate_bollinger(self, prices: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """计算布林带"""
        middle = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()
        upper = middle + 2 * std
        lower = middle - 2 * std
        position = (prices - lower) / (upper - lower + 1e-9)
        return {"upper": upper, "middle": middle, "lower": lower, "position": position}
    
    def predict(
        self,
        model: Any,
        features: pd.DataFrame,
        date: Optional[str] = None
    ) -> pd.Series:
        """
        执行模型预测
        
        Args:
            model: 训练好的模型
            features: 特征数据
            date: 预测日期
            
        Returns:
            预测结果 Series (index=symbol, value=prediction)
        """
        logger.info(f"Running prediction for {len(features)} samples")
        
        if features.empty:
            return pd.Series(dtype=float)
        
        # 准备特征矩阵
        feature_cols = [col for col in self.feature_config["features"] if col in features.columns]
        
        if not feature_cols:
            logger.error("No valid features found in data")
            return pd.Series(dtype=float)
        
        X = features[feature_cols].fillna(0)
        
        # 执行预测
        try:
            predictions = model.predict(X)
            
            # 构建结果 Series
            result = pd.Series(
                predictions,
                index=features.index,
                name="prediction"
            )
            
            # 关联股票代码
            if "symbol" in features.columns:
                result = result.set_axis(features["symbol"])
            
            logger.info(f"Prediction completed. Mean: {result.mean():.6f}, Std: {result.std():.6f}")
            return result
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            raise
    
    def generate_signals(
        self,
        predictions: pd.Series,
        top_k: int = 50,
        n_drop: int = 5
    ) -> Dict[str, List[str]]:
        """
        生成交易信号
        
        Args:
            predictions: 预测结果
            top_k: 买入数量
            n_drop: 卖出数量
            
        Returns:
            交易信号字典 {buy: [...], sell: [...], hold: [...]}
        """
        logger.info(f"Generating signals: top_k={top_k}, n_drop={n_drop}")
        
        if predictions.empty:
            return {"buy": [], "sell": [], "hold": []}
        
        # 按预测值排序
        sorted_preds = predictions.sort_values(ascending=False)
        
        # 选股
        buy_list = sorted_preds.head(top_k).index.tolist()
        sell_list = sorted_preds.tail(n_drop).index.tolist()
        hold_list = sorted_preds.iloc[n_drop:-top_k].index.tolist() if len(sorted_preds) > top_k + n_drop else []
        
        signals = {
            "buy": buy_list,
            "sell": sell_list,
            "hold": hold_list,
            "generated_at": datetime.now().isoformat(),
            "total_stocks": len(predictions),
        }
        
        logger.info(f"Signals generated: {len(buy_list)} buy, {len(sell_list)} sell, {len(hold_list)} hold")
        return signals
    
    def save_signals(
        self,
        signals: Dict,
        date: str,
        format: str = "json"
    ) -> str:
        """
        保存交易信号
        
        Args:
            signals: 信号字典
            date: 交易日期
            format: 输出格式 (json/csv/parquet)
            
        Returns:
            保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"signals_{date}_{timestamp}"
        
        if format == "json":
            file_path = self.output_dir / f"{base_name}.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(signals, f, indent=2, ensure_ascii=False)
        
        elif format == "csv":
            # 分别保存买卖列表
            for signal_type in ["buy", "sell", "hold"]:
                if signal_type in signals and signals[signal_type]:
                    file_path = self.output_dir / f"{base_name}_{signal_type}.csv"
                    df = pd.DataFrame({"symbol": signals[signal_type]})
                    df.to_csv(file_path, index=False)
            file_path = self.output_dir / f"{base_name}_summary.csv"
        
        elif format == "parquet":
            file_path = self.output_dir / f"{base_name}.parquet"
            df = pd.DataFrame({
                "symbol": list(signals.get("buy", [])) + list(signals.get("sell", [])),
                "signal": ["buy"] * len(signals.get("buy", [])) + ["sell"] * len(signals.get("sell", []))
            })
            df.to_parquet(file_path, index=False)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Signals saved to: {file_path}")
        return str(file_path)
    
    def run_full_pipeline(
        self,
        date: Optional[str] = None,
        universe: str = "csi300",
        top_k: int = 50,
        n_drop: int = 5,
        exp_id: Optional[str] = None,
        model_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        运行完整的预测流水线
        
        Args:
            date: 预测日期
            universe: 股票池
            top_k: 持仓数量
            n_drop: 调出数量
            exp_id: 实验 ID
            model_path: 模型路径
            
        Returns:
            完整结果字典
        """
        logger.info("="*60)
        logger.info("Starting Daily Prediction Pipeline")
        logger.info("="*60)
        
        if date is None:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        results = {
            "date": date,
            "universe": universe,
            "status": "running",
            "steps": {},
        }
        
        try:
            # Step 1: 加载模型
            logger.info("\n[Step 1] Loading model...")
            model = self.load_model(model_path=model_path, exp_id=exp_id)
            results["steps"]["load_model"] = "success"
            
            # Step 2: 获取数据
            logger.info("\n[Step 2] Fetching market data...")
            raw_data = self.fetch_latest_data(date=date, universe=universe)
            results["steps"]["fetch_data"] = f"fetched {len(raw_data)} records"
            
            # Step 3: 计算特征
            logger.info("\n[Step 3] Calculating features...")
            features = self.calculate_features(raw_data)
            results["steps"]["calculate_features"] = f"{features['symbol'].nunique() if not features.empty else 0} stocks"
            
            # Step 4: 执行预测
            logger.info("\n[Step 4] Running prediction...")
            predictions = self.predict(model, features, date)
            results["steps"]["predict"] = f"{len(predictions)} predictions"
            
            # Step 5: 生成信号
            logger.info("\n[Step 5] Generating trading signals...")
            signals = self.generate_signals(predictions, top_k=top_k, n_drop=n_drop)
            results["steps"]["generate_signals"] = f"{len(signals['buy'])} buy, {len(signals['sell'])} sell"
            
            # Step 6: 保存信号
            logger.info("\n[Step 6] Saving signals...")
            signal_file = self.save_signals(signals, date)
            results["steps"]["save_signals"] = signal_file
            
            # 附加信息
            results["status"] = "completed"
            results["signal_file"] = signal_file
            results["predictions_summary"] = {
                "count": len(predictions),
                "mean": float(predictions.mean()) if len(predictions) > 0 else None,
                "std": float(predictions.std()) if len(predictions) > 0 else None,
                "max": float(predictions.max()) if len(predictions) > 0 else None,
                "min": float(predictions.min()) if len(predictions) > 0 else None,
            }
            results["top_10_stocks"] = predictions.nlargest(10).to_dict() if len(predictions) > 0 else {}
            
            logger.info("\n" + "="*60)
            logger.info("Pipeline completed successfully!")
            logger.info(f"Signal file: {signal_file}")
            logger.info("="*60 + "\n")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            results["status"] = "failed"
            results["error"] = str(e)
        
        # 保存完整结果
        result_file = self.output_dir / f"pipeline_result_{date}.json"
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        
        return results


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Daily Prediction Pipeline")
    parser.add_argument("--model-dir", type=str, required=True, help="模型目录")
    parser.add_argument("--date", type=str, default=None, help="预测日期 (YYYY-MM-DD)")
    parser.add_argument("--universe", type=str, default="csi300", help="股票池")
    parser.add_argument("--top-k", type=int, default=50, help="持仓数量")
    parser.add_argument("--n-drop", type=int, default=5, help="调出数量")
    parser.add_argument("--exp-id", type=str, default=None, help="实验 ID")
    parser.add_argument("--output-dir", type=str, default="./predictions", help="输出目录")
    parser.add_argument("--provider", type=str, default="akshare", help="数据源")
    
    args = parser.parse_args()
    
    # 创建预测器
    predictor = DailyPredictor(
        model_dir=args.model_dir,
        data_provider=args.provider,
        output_dir=Path(args.output_dir)
    )
    
    # 运行流水线
    results = predictor.run_full_pipeline(
        date=args.date,
        universe=args.universe,
        top_k=args.top_k,
        n_drop=args.n_drop,
        exp_id=args.exp_id
    )
    
    # 打印摘要
    print("\n" + "="*60)
    print("PREDICTION SUMMARY")
    print("="*60)
    print(f"Date: {results['date']}")
    print(f"Status: {results['status']}")
    if results['status'] == 'completed':
        print(f"Buy signals: {len(json.loads(json.dumps(results)).get('top_10_stocks', {}))} shown (top 10)")
        print(f"Signal file: {results.get('signal_file')}")
    else:
        print(f"Error: {results.get('error')}")
    print("="*60)
