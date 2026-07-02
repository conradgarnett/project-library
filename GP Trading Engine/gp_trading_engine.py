"""
Version 2 GP Trading Research Engine for SPY - FIXED VERSION

Key fixes:
1. Proper position-return alignment (no look-ahead bias)
2. Correct transaction cost application (per-trade, not flat drag)
3. Fixed equity curve calculation
4. Proper validation and error handling
"""

from __future__ import annotations

import json
import random
import warnings
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode

import numpy as np
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib


warnings.filterwarnings("ignore")

STRATEGY_VAULT_PATH = Path("strategy_vault.json")


class DataLayer:
    """Pulls real SPY market data and prepares it for modeling."""

    @staticmethod
    def _prepare_ohlcv(df: pd.DataFrame, symbol: str, source: str) -> pd.DataFrame:
        if df.empty:
            raise RuntimeError(f"No data returned from {source} for {symbol}.")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df.rename(columns=str.title)
        required = ["Open", "High", "Low", "Close", "Volume"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise RuntimeError(f"{source} data is missing required columns: {missing}")

        df = df[required].copy()
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        df["returns"] = df["Close"].pct_change()
        df["log_returns"] = np.log(df["Close"] / df["Close"].shift(1))
        df["volatility"] = df["returns"].rolling(20).std()
        df = df.replace([np.inf, -np.inf], np.nan).dropna()

        print(
            f"Loaded {len(df)} real {symbol} bars from {source}: "
            f"{df.index.min().date()} to {df.index.max().date()}"
        )
        return df

    @staticmethod
    def _fetch_from_yahoo(
        symbol: str = "SPY",
        start: str = "2001-01-01",
        end: Optional[str] = None,
        interval: str = "1d",
        auto_adjust: bool = True,
    ) -> pd.DataFrame:
        df = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=auto_adjust,
            progress=False,
            threads=True,
        )
        return DataLayer._prepare_ohlcv(df, symbol, "Yahoo Finance")

    @staticmethod
    def _fetch_from_stooq(
        symbol: str = "SPY",
        start: str = "2001-01-01",
        end: Optional[str] = None,
    ) -> pd.DataFrame:
        stooq_symbol = symbol.lower()
        if not stooq_symbol.endswith(".us"):
            stooq_symbol = f"{stooq_symbol}.us"

        params = {
            "s": stooq_symbol,
            "d1": start.replace("-", ""),
            "d2": (end or pd.Timestamp.utcnow().strftime("%Y-%m-%d")).replace("-", ""),
            "i": "d",
        }
        url = f"https://stooq.com/q/d/l/?{urlencode(params)}"
        csv_text = pd.read_csv(url).to_csv(index=False)
        df = pd.read_csv(StringIO(csv_text), parse_dates=["Date"], index_col="Date")
        return DataLayer._prepare_ohlcv(df, symbol, "Stooq")

    @staticmethod
    def fetch_spy_data(
        symbol: str = "SPY",
        start: str = "2001-01-01",
        end: Optional[str] = None,
        interval: str = "1d",
        auto_adjust: bool = True,
        source: str = "auto",
    ) -> pd.DataFrame:
        """
        Fetch real SPY data from free sources.

        For a 2001-to-present backtest, use interval="1d". Yahoo Finance only
        offers intraday intervals for short recent windows, not from 2001.
        """
        if interval != "1d" and start < "2020-01-01":
            raise ValueError(
                "Free providers do not provide long-history intraday SPY bars. "
                "Use interval='1d' for 2001-present, or connect a paid intraday "
                "data provider."
            )

        if source not in {"auto", "yahoo", "stooq"}:
            raise ValueError("source must be one of: auto, yahoo, stooq")

        print(
            f"Fetching real {symbol} data from {start} to {end or 'present'} "
            f"({interval}, source={source})..."
        )

        if source == "stooq":
            if interval != "1d":
                raise ValueError("Stooq fallback in this engine supports daily bars only.")
            return DataLayer._fetch_from_stooq(symbol=symbol, start=start, end=end)

        try:
            return DataLayer._fetch_from_yahoo(
                symbol=symbol,
                start=start,
                end=end,
                interval=interval,
                auto_adjust=auto_adjust,
            )
        except Exception as yahoo_error:
            if source == "yahoo" or interval != "1d":
                raise

            print(f"Yahoo Finance failed: {yahoo_error}")
            print("Falling back to Stooq daily CSV data...")
            return DataLayer._fetch_from_stooq(symbol=symbol, start=start, end=end)


class FeatureEngine:
    """Transforms price data into predictive signals."""

    @staticmethod
    def build_features(df: pd.DataFrame) -> pd.DataFrame:
        print("Building features...")
        features = pd.DataFrame(index=df.index)

        features["ret1"] = df["Close"].pct_change(1)
        features["ret5"] = df["Close"].pct_change(5)
        features["mom10"] = df["Close"].pct_change(10)
        features["vol"] = df["returns"].rolling(20).std()

        ma5 = df["Close"].rolling(5).mean()
        ma20 = df["Close"].rolling(20).mean()
        features["ma_fast"] = (df["Close"] - ma5) / ma5
        features["ma_slow"] = (df["Close"] - ma20) / ma20

        features = features.replace([np.inf, -np.inf], np.nan).dropna()

        # Causal z-score: normalize each feature using only statistics available
        # up to the *prior* bar (expanding window, then shift(1)). The previous
        # implementation used the global mean/std over the entire series, which
        # leaks future information into past observations (look-ahead bias) and
        # inflates every backtest run through this path.
        print("Normalizing features with causal (expanding) z-scores...")
        min_periods = 60
        normalized = pd.DataFrame(index=features.index)
        for col in features.columns:
            past_mean = features[col].expanding(min_periods=min_periods).mean().shift(1)
            past_std = features[col].expanding(min_periods=min_periods).std().shift(1)
            normalized[col] = (features[col] - past_mean) / past_std.where(past_std > 1e-8)
        features = normalized.replace([np.inf, -np.inf], np.nan).dropna()

        print(f"Built {len(features.columns)} features with {len(features)} samples")
        return features


@dataclass
class TreeNode:
    """Mathematical expression tree node."""

    op: str
    left: Optional["TreeNode"] = None
    right: Optional["TreeNode"] = None

    def __str__(self, indent: int = 0) -> str:
        text = "  " * indent + self.op + "\n"
        if self.left:
            text += self.left.__str__(indent + 1)
        if self.right:
            text += self.right.__str__(indent + 1)
        return text

    def to_expr(self) -> str:
        if self.left is None and self.right is None:
            return self.op
        if self.right is None:
            return f"{self.op}({self.left.to_expr()})"
        return f"{self.op}({self.left.to_expr()}, {self.right.to_expr()})"

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "left": self.left.to_dict() if self.left else None,
            "right": self.right.to_dict() if self.right else None,
        }

    @staticmethod
    def from_dict(data: dict) -> "TreeNode":
        return TreeNode(
            op=data["op"],
            left=TreeNode.from_dict(data["left"]) if data.get("left") else None,
            right=TreeNode.from_dict(data["right"]) if data.get("right") else None,
        )


class GPTree:
    """Genetic Programming tree generator and manipulator."""

    BINARY_OPS = ["add", "sub", "mul", "div"]
    UNARY_OPS = ["tanh"]

    def __init__(self, feature_names: List[str]):
        self.feature_names = feature_names
        self.all_ops = self.BINARY_OPS + self.UNARY_OPS

    def generate_random_tree(self, max_depth: int = 3, curr_depth: int = 0) -> TreeNode:
        if curr_depth >= max_depth or (curr_depth > 0 and random.random() < 0.3):
            return TreeNode(op=random.choice(self.feature_names))

        op = random.choice(self.all_ops)
        left = self.generate_random_tree(max_depth, curr_depth + 1)
        if op in self.UNARY_OPS:
            return TreeNode(op=op, left=left)

        right = self.generate_random_tree(max_depth, curr_depth + 1)
        return TreeNode(op=op, left=left, right=right)

    def mutate_tree(self, node: TreeNode, mutation_rate: float = 0.3) -> TreeNode:
        if random.random() < mutation_rate:
            return self.generate_random_tree(max_depth=2)

        new_node = TreeNode(op=node.op)
        if node.left:
            new_node.left = self.mutate_tree(node.left, mutation_rate)
        if node.right:
            new_node.right = self.mutate_tree(node.right, mutation_rate)
        return new_node


class TreeEvaluator:
    """Converts GP trees into numerical signals."""

    @staticmethod
    def safe_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        return np.where(np.abs(b) < 1e-8, 0.0, a / b)

    @staticmethod
    def evaluate_tree(node: TreeNode, features: pd.DataFrame) -> np.ndarray:
        if node.left is None and node.right is None:
            return features[node.op].values if node.op in features.columns else np.zeros(len(features))

        if node.op == "sin":
            return np.sin(TreeEvaluator.evaluate_tree(node.left, features))
        if node.op == "cos":
            return np.cos(TreeEvaluator.evaluate_tree(node.left, features))
        if node.op == "tanh":
            return np.tanh(TreeEvaluator.evaluate_tree(node.left, features))

        left_val = TreeEvaluator.evaluate_tree(node.left, features)
        right_val = TreeEvaluator.evaluate_tree(node.right, features)

        if node.op == "add":
            return left_val + right_val
        if node.op == "sub":
            return left_val - right_val
        if node.op == "mul":
            return left_val * right_val
        if node.op == "div":
            return TreeEvaluator.safe_div(left_val, right_val)

        return np.zeros(len(features))


class SignalExecutor:
    """Transforms GP output into trading positions."""

    @staticmethod
    def signal_to_position(signal: np.ndarray, scale: float = 3.0) -> np.ndarray:
        signal_clipped = np.clip(signal, -10, 10)
        return np.tanh(signal_clipped * 5.0)

    @staticmethod
    def apply_risk_controls(
        position: np.ndarray,
        market_returns: np.ndarray,
        mode: str = "long_short",
        max_exposure: float = 1.0,
        target_vol: Optional[float] = None,
        vol_window: int = 20,
        annualization: float = 252,
    ) -> np.ndarray:
        """Apply position-level controls before the backtest loop."""
        if len(position) != len(market_returns):
            min_len = min(len(position), len(market_returns))
            position = position[:min_len]
            market_returns = market_returns[:min_len]

        controlled = np.clip(position, -max_exposure, max_exposure)

        if mode == "long_flat":
            controlled = np.clip(controlled, 0.0, max_exposure)
        elif mode == "short_flat":
            controlled = np.clip(controlled, -max_exposure, 0.0)
        elif mode != "long_short":
            raise ValueError("mode must be one of: long_short, long_flat, short_flat")

        if target_vol is not None and target_vol > 0:
            returns_series = pd.Series(market_returns)
            realized_vol = returns_series.rolling(vol_window).std().shift(1) * np.sqrt(annualization)
            vol_scalar = target_vol / realized_vol.replace(0, np.nan)
            vol_scalar = vol_scalar.clip(0.0, 1.0).fillna(1.0).values
            controlled = controlled * vol_scalar

        return np.clip(controlled, -max_exposure, max_exposure)


def best_strategy_signal(features: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """
    Hard-coded version of the best evolved strategy from the seeded 10-gen run.

    GP expression:
    sub(cos(sin(tanh(mul(sin(mom10), div(mul(ma_slow, add(ma_slow, vol)), add(ret1, ret1)))))), ret1)
    """
    ret1 = features["ret1"].values
    mom10 = features["mom10"].values
    ma_slow = features["ma_slow"].values
    vol = features["vol"].values

    numerator = ma_slow * (ma_slow + vol)
    denominator = ret1 + ret1
    safe_ratio = TreeEvaluator.safe_div(numerator, denominator)

    signal = np.cos(np.sin(np.tanh(np.sin(mom10) * safe_ratio))) - ret1
    position = SignalExecutor.signal_to_position(signal)

    return signal, position


class BacktestEngine:
    """Simulates trading performance and computes fitness."""

    @staticmethod
    def compute_sharpe(returns: np.ndarray, annualization: float = 252) -> float:
        if len(returns) < 2:
            return 0.0

        mean_ret = np.mean(returns)
        std_ret = np.std(returns)
        if std_ret < 1e-8:
            return 0.0

        sharpe = (mean_ret / std_ret) * np.sqrt(annualization)
        return float(np.clip(sharpe, -10, 10))

    @staticmethod
    def compute_drawdown(returns: np.ndarray) -> float:
        if len(returns) < 2:
            return 0.0

        cum_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cum_returns)
        drawdown = (cum_returns - running_max) / running_max
        return float(np.min(drawdown))

    @staticmethod
    def compute_calmar(total_return: float, drawdown: float, n_periods: int, annualization: float) -> float:
        if n_periods < 2 or abs(drawdown) < 1e-8:
            return 0.0

        years = n_periods / annualization
        if years <= 0 or total_return <= -1.0:
            return 0.0

        cagr = (1 + total_return) ** (1 / years) - 1
        return float(np.clip(cagr / abs(drawdown), -10, 10))

    @staticmethod
    def compute_cagr(total_return: float, n_periods: int, annualization: float) -> float:
        if n_periods < 2 or total_return <= -1.0:
            return 0.0
        years = n_periods / annualization
        if years <= 0:
            return 0.0
        return float((1 + total_return) ** (1 / years) - 1)

    @staticmethod
    def compute_turnover(positions: np.ndarray) -> float:
        if len(positions) < 2:
            return 0.0
        return float(np.mean(np.abs(np.diff(positions))))

    @staticmethod
    def backtest_strategy(
        positions: np.ndarray,
        market_returns: np.ndarray,
        turnover_cost: float = 0.0001,
        annualization: float = 252,
        initial_capital: float = 10_000,
        drawdown_throttle: Optional[float] = None,
        throttle_exposure: float = 0.25,
        calmar_weight: float = 0.75,
        return_weight: float = 2.0,
        cagr_weight: float = 4.0,
        drawdown_weight: float = 1.0,
    ) -> dict:
        """
        FIXED BACKTEST ENGINE
        
        Key fixes:
        1. Proper position-return alignment (no look-ahead bias)
        2. Transaction costs applied per-trade, not flat drag
        3. Single equity calculation (no redundancy)
        4. Proper validation
        """
        # Ensure equal length
        if len(positions) != len(market_returns):
            min_len = min(len(positions), len(market_returns))
            positions = positions[:min_len]
            market_returns = market_returns[:min_len]
        
        # Handle edge cases
        if len(positions) < 2:
            return {
                "win_rate": 0,
                "avg_return": 0,
                "fitness": -999,
                "sharpe": 0,
                "calmar": 0,
                "cagr": 0,
                "drawdown": 0,
                "turnover": 0,
                "cost_drag": 0,
                "initial_capital": initial_capital,
                "final_equity": initial_capital,
                "pnl": 0,
                "total_return": 0,
                "equity_curve": np.array([initial_capital]),
                "returns": np.array([]),
            }

        effective_positions = positions.copy()
        strategy_returns = []
        equity = initial_capital
        peak_equity = initial_capital
        equity_curve = [initial_capital]
        
        prev_position = 0.0
        total_transaction_cost = 0.0

        # CRITICAL FIX: Proper position-return alignment
        # Position at time t should capture return from t to t+1
        # But returns[t] is the return from t-1 to t
        # So we use position[t] with returns[t+1], OR shift positions
        # Here we shift positions: position computed at t applies to returns at t+1
        
        for i in range(len(market_returns) - 1):  # -1 because we look ahead
            # Position computed from features at time i
            position = effective_positions[i]
            
            # Apply drawdown throttle if needed
            current_drawdown = (equity - peak_equity) / peak_equity if peak_equity > 0 else 0.0
            if drawdown_throttle is not None and current_drawdown <= -abs(drawdown_throttle):
                position *= throttle_exposure
                effective_positions[i] = position
            
            # Calculate transaction cost for position change
            position_change = abs(position - prev_position)
            transaction_cost = position_change * turnover_cost
            total_transaction_cost += transaction_cost
            
            # Strategy return = position * next period's market return - transaction cost
            # This is the return from time i to i+1
            gross_return = position * market_returns[i + 1]
            net_return = gross_return - transaction_cost
            strategy_returns.append(net_return)
            
            # Update equity
            equity = equity * (1 + net_return)
            equity_curve.append(equity)
            peak_equity = max(peak_equity, equity)
            
            prev_position = position

        strategy_returns = np.array(strategy_returns)
        equity_curve = np.array(equity_curve)
        
        # Validate returns
        if not np.isfinite(strategy_returns).all() or len(strategy_returns) < 10:
            return {
                "win_rate": 0,
                "avg_return": 0,
                "fitness": -999,
                "invalid": True,
                "sharpe": 0,
                "calmar": 0,
                "cagr": 0,
                "drawdown": 0,
                "turnover": 0,
                "cost_drag": 0,
                "initial_capital": initial_capital,
                "final_equity": initial_capital,
                "pnl": 0,
                "total_return": 0,
                "equity_curve": equity_curve,
                "returns": strategy_returns,
            }
        
        # Calculate metrics
        sharpe = BacktestEngine.compute_sharpe(strategy_returns, annualization)
        drawdown = BacktestEngine.compute_drawdown(strategy_returns)
        
        final_equity = float(equity_curve[-1])
        pnl = final_equity - initial_capital
        total_return = (final_equity / initial_capital) - 1
        
        cagr = BacktestEngine.compute_cagr(total_return, len(strategy_returns), annualization)
        calmar = BacktestEngine.compute_calmar(total_return, drawdown, len(strategy_returns), annualization)
        turnover = BacktestEngine.compute_turnover(effective_positions)
        
        # Average transaction cost per period
        cost_drag = total_transaction_cost / len(strategy_returns) if len(strategy_returns) > 0 else 0
        
        win_rate = float(np.mean(strategy_returns > 0))
        avg_return = float(np.mean(strategy_returns))
        
        # Fitness calculation
        fitness = (
            sharpe
            + calmar_weight * calmar
            + cagr_weight * cagr
            + return_weight * float(np.clip(total_return, -1.0, 2.0))
            + drawdown_weight * drawdown
            - (cost_drag * 1000)
        )

        return {
            "sharpe": sharpe,
            "calmar": calmar,
            "cagr": cagr,
            "drawdown": drawdown,
            "turnover": turnover,
            "cost_drag": cost_drag,
            "fitness": float(fitness),
            "initial_capital": initial_capital,
            "final_equity": final_equity,
            "pnl": pnl,
            "total_return": float(total_return),
            "win_rate": win_rate,
            "avg_return": avg_return,
            "equity_curve": equity_curve[1:],  # Exclude initial capital
            "returns": strategy_returns,
        }

    @staticmethod
    def benchmark_buy_hold(
        market_returns: np.ndarray,
        annualization: float = 252,
        initial_capital: float = 10_000,
    ) -> dict:
        positions = np.ones(len(market_returns))
        return BacktestEngine.backtest_strategy(
            positions,
            market_returns,
            turnover_cost=0.0,
            annualization=annualization,
            initial_capital=initial_capital,
            calmar_weight=0.0,
            return_weight=0.0,
            cagr_weight=0.0,
            drawdown_weight=0.0,
        )


@dataclass
class Strategy:
    """Individual strategy in the population."""

    tree: TreeNode
    sharpe: float = 0.0
    calmar: float = 0.0
    cagr: float = 0.0
    drawdown: float = 0.0
    fitness: float = 0.0
    turnover: float = 0.0
    final_equity: float = 0.0
    pnl: float = 0.0
    total_return: float = 0.0
    win_rate: float = 0.0

    def get_expr(self) -> str:
        return self.tree.to_expr()


class StrategyVault:
    """Persists best evolved strategies so future runs can start smarter."""

    @staticmethod
    def _tree_uses_known_features(node: TreeNode, feature_names: set[str]) -> bool:
        known_ops = set(GPTree.BINARY_OPS + GPTree.UNARY_OPS)
        if node.left is None and node.right is None:
            return node.op in feature_names
        if node.op not in known_ops:
            return False
        left_ok = StrategyVault._tree_uses_known_features(node.left, feature_names) if node.left else True
        right_ok = StrategyVault._tree_uses_known_features(node.right, feature_names) if node.right else True
        return left_ok and right_ok

    @staticmethod
    def load_records(path: Path = STRATEGY_VAULT_PATH) -> list[dict]:
        if not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (json.JSONDecodeError, OSError):
            return []
        return data if isinstance(data, list) else []

    @staticmethod
    def load_champions(
        feature_names: list[str],
        path: Path = STRATEGY_VAULT_PATH,
        max_champions: int = 10,
    ) -> list[TreeNode]:
        feature_set = set(feature_names)
        champions = []

        for record in StrategyVault.load_records(path):
            tree_data = record.get("tree")
            if not tree_data:
                continue
            try:
                tree = TreeNode.from_dict(tree_data)
            except (KeyError, TypeError):
                continue
            if StrategyVault._tree_uses_known_features(tree, feature_set):
                champions.append(tree)
            if len(champions) >= max_champions:
                break

        return champions

    @staticmethod
    def save_strategy(
        strategy: Strategy,
        metadata: dict,
        path: Path = STRATEGY_VAULT_PATH,
        max_records: int = 100,
    ) -> None:
        records = StrategyVault.load_records(path)
        expression = strategy.get_expr()
        records = [record for record in records if record.get("expression") != expression]
        records.append(
            {
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "expression": expression,
                "tree": strategy.tree.to_dict(),
                "metrics": {
                    "fitness": strategy.fitness,
                    "sharpe": strategy.sharpe,
                    "calmar": strategy.calmar,
                    "cagr": strategy.cagr,
                    "drawdown": strategy.drawdown,
                    "turnover": strategy.turnover,
                    "final_equity": strategy.final_equity,
                    "pnl": strategy.pnl,
                    "total_return": strategy.total_return,
                    "win_rate": strategy.win_rate,
                },
                "metadata": metadata,
            }
        )
        records.sort(key=lambda record: record.get("metrics", {}).get("fitness", -np.inf), reverse=True)

        with path.open("w", encoding="utf-8") as file:
            json.dump(records[:max_records], file, indent=2)

    @staticmethod
    def get_vault_stats(path: Path = STRATEGY_VAULT_PATH) -> dict:
        """Get statistics about the strategy vault for learning tracking."""
        records = StrategyVault.load_records(path)
        if not records:
            return {"count": 0, "best_fitness": 0.0, "avg_fitness": 0.0}
        
        fitnesses = [r.get("metrics", {}).get("fitness", 0.0) for r in records]
        return {
            "count": len(records),
            "best_fitness": max(fitnesses),
            "avg_fitness": np.mean(fitnesses),
            "top_5_avg": np.mean(fitnesses[:5]) if len(fitnesses) >= 5 else np.mean(fitnesses)
        }


class MonteCarloSimulator:
    """Runs Monte Carlo simulations for strategy robustness testing."""
    
    @staticmethod
    def run_simulation(
        strategy: Strategy,
        features: pd.DataFrame,
        market_returns: np.ndarray,
        n_simulations: int = 1000,
        bootstrap: bool = True,
        annualization: float = 252,
        initial_capital: float = 10_000,
    ) -> dict:
        """
        Run Monte Carlo simulations of the strategy.
        """
        print(f"\nRunning {n_simulations} Monte Carlo simulations...")
        
        # Get base signal and position
        signal = TreeEvaluator.evaluate_tree(strategy.tree, features)
        position = SignalExecutor.signal_to_position(signal)
        position = SignalExecutor.apply_risk_controls(
            position,
            market_returns,
            mode="long_short",
            max_exposure=1.0,
            annualization=annualization,
        )
        
        final_equities = []
        sharpes = []
        drawdowns = []
        returns_list = []
        
        for i in range(n_simulations):
            if bootstrap:
                # Bootstrap: sample returns with replacement
                sim_returns = np.random.choice(market_returns, size=len(market_returns), replace=True)
            else:
                # Randomize: shuffle returns
                sim_returns = np.random.permutation(market_returns)
            
            # Run backtest with simulated returns
            results = BacktestEngine.backtest_strategy(
                position,
                sim_returns,
                annualization=annualization,
                initial_capital=initial_capital,
                calmar_weight=0.0,
                return_weight=0.0,
                cagr_weight=0.0,
                drawdown_weight=0.0,
            )
            
            if results.get("invalid"):
                continue
                
            final_equities.append(results["final_equity"])
            sharpes.append(results["sharpe"])
            drawdowns.append(results["drawdown"])
            returns_list.append(results["total_return"])
        
        final_equities = np.array(final_equities)
        sharpes = np.array(sharpes)
        drawdowns = np.array(drawdowns)
        returns_list = np.array(returns_list)
        
        return {
            "final_equities": final_equities,
            "sharpes": sharpes,
            "drawdowns": drawdowns,
            "returns": returns_list,
            "stats": {
                "equity_mean": np.mean(final_equities),
                "equity_median": np.median(final_equities),
                "equity_std": np.std(final_equities),
                "equity_5th": np.percentile(final_equities, 5),
                "equity_95th": np.percentile(final_equities, 95),
                "sharpe_mean": np.mean(sharpes),
                "sharpe_median": np.median(sharpes),
                "return_mean": np.mean(returns_list),
                "return_median": np.median(returns_list),
                "prob_profit": np.mean(final_equities > initial_capital),
            }
        }
    
    @staticmethod
    def plot_monte_carlo_results(
        mc_results: dict,
        strategy_name: str,
        save_path: Path,
        initial_capital: float = 10_000,
    ) -> None:
        """Create comprehensive Monte Carlo visualization."""
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle(f'Monte Carlo Simulation Results: {strategy_name}', fontsize=14, fontweight='bold')
        
        # 1. Final Equity Distribution
        ax = axes[0, 0]
        ax.hist(mc_results["final_equities"], bins=50, alpha=0.7, color='steelblue', edgecolor='black')
        ax.axvline(initial_capital, color='red', linestyle='--', linewidth=2, label='Initial Capital')
        ax.axvline(mc_results["stats"]["equity_median"], color='green', linestyle='-', linewidth=2, label='Median')
        ax.axvline(mc_results["stats"]["equity_5th"], color='orange', linestyle=':', linewidth=2, label='5th %ile')
        ax.axvline(mc_results["stats"]["equity_95th"], color='orange', linestyle=':', linewidth=2, label='95th %ile')
        ax.set_xlabel('Final Equity ($)', fontsize=10)
        ax.set_ylabel('Frequency', fontsize=10)
        ax.set_title('Distribution of Final Equity', fontsize=11, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # 2. Sharpe Ratio Distribution
        ax = axes[0, 1]
        ax.hist(mc_results["sharpes"], bins=50, alpha=0.7, color='forestgreen', edgecolor='black')
        ax.axvline(mc_results["stats"]["sharpe_median"], color='red', linestyle='-', linewidth=2, label='Median')
        ax.axvline(0, color='gray', linestyle='--', linewidth=1)
        ax.set_xlabel('Sharpe Ratio', fontsize=10)
        ax.set_ylabel('Frequency', fontsize=10)
        ax.set_title('Distribution of Sharpe Ratios', fontsize=11, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # 3. Drawdown Distribution
        ax = axes[1, 0]
        ax.hist(mc_results["drawdowns"] * 100, bins=50, alpha=0.7, color='crimson', edgecolor='black')
        ax.axvline(np.median(mc_results["drawdowns"]) * 100, color='blue', linestyle='-', linewidth=2, label='Median')
        ax.set_xlabel('Maximum Drawdown (%)', fontsize=10)
        ax.set_ylabel('Frequency', fontsize=10)
        ax.set_title('Distribution of Maximum Drawdowns', fontsize=11, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # 4. Return Distribution
        ax = axes[1, 1]
        ax.hist(mc_results["returns"] * 100, bins=50, alpha=0.7, color='purple', edgecolor='black')
        ax.axvline(0, color='red', linestyle='--', linewidth=2, label='Break-even')
        ax.axvline(mc_results["stats"]["return_median"] * 100, color='green', linestyle='-', linewidth=2, label='Median')
        ax.set_xlabel('Total Return (%)', fontsize=10)
        ax.set_ylabel('Frequency', fontsize=10)
        ax.set_title('Distribution of Total Returns', fontsize=11, fontweight='bold')
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # Add summary statistics text
        stats_text = (
            f"Simulations: {len(mc_results['final_equities'])}\n"
            f"Prob(Profit): {mc_results['stats']['prob_profit']*100:.1f}%\n"
            f"Median Return: {mc_results['stats']['return_median']*100:.1f}%\n"
            f"Median Sharpe: {mc_results['stats']['sharpe_median']:.2f}"
        )
        fig.text(0.02, 0.02, stats_text, fontsize=9, family='monospace',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"Monte Carlo plot saved to {save_path}")

    @staticmethod
    def run_multi_strategy_simulation(
        strategies,
        features,
        market_returns,
        n_simulations=1000,
        initial_capital=10000,
    ):
        print(f"\nRunning MULTI-STRATEGY Monte Carlo ({len(strategies)} strategies)...")

        all_final_equities = []
        all_returns = []

        for strat in strategies:
            signal = TreeEvaluator.evaluate_tree(strat.tree, features)
            position = SignalExecutor.signal_to_position(signal)

            sims_per_strat = max(1, n_simulations // len(strategies))

            for _ in range(sims_per_strat):
                sim_returns = np.random.choice(
                    market_returns,
                    size=len(market_returns),
                    replace=True
                )

                results = BacktestEngine.backtest_strategy(
                    position,
                    sim_returns,
                    initial_capital=initial_capital,
                    calmar_weight=0.0,
                    return_weight=0.0,
                    cagr_weight=0.0,
                    drawdown_weight=0.0,
                )

                if not results.get("invalid"):
                    all_final_equities.append(results["final_equity"])
                    all_returns.append(results["total_return"])

        return {
            "equity": np.array(all_final_equities),
            "returns": np.array(all_returns),
        }


class GeneticEvolutionEngine:
    """Handles population evolution, selection, mutation, and elitism."""
    
    def tree_size(self, node):
        if node is None:
            return 0
        return 1 + self.tree_size(node.left) + self.tree_size(node.right)

    def tree_depth(self, node):
        if node is None:
            return 0
        return 1 + max(self.tree_depth(node.left), self.tree_depth(node.right))

    def __init__(
        self,
        feature_names: List[str],
        population_size: int = 50,
        elite_size: int = 5,
        mutation_rate: float = 0.3,
        annualization: float = 252,
        initial_capital: float = 10_000,
        position_mode: str = "long_short",
        max_exposure: float = 1.0,
        target_vol: Optional[float] = None,
        vol_window: int = 20,
        drawdown_throttle: Optional[float] = None,
        throttle_exposure: float = 0.25,
        calmar_weight: float = 0.75,
        return_weight: float = 2.0,
    ):
        self.feature_names = feature_names
        self.population_size = population_size
        self.elite_size = elite_size
        self.mutation_rate = mutation_rate
        self.annualization = annualization
        self.initial_capital = initial_capital
        self.position_mode = position_mode
        self.max_exposure = max_exposure
        self.target_vol = target_vol
        self.vol_window = vol_window
        self.drawdown_throttle = drawdown_throttle
        self.throttle_exposure = throttle_exposure
        self.calmar_weight = calmar_weight
        self.return_weight = return_weight
        self.gp_tree = GPTree(feature_names)
        self.population: List[Strategy] = []

    def initialize_population(self, seed_trees: Optional[list[TreeNode]] = None) -> None:
        print(f"Initializing population of {self.population_size} strategies...")
        self.population = []
        seed_trees = seed_trees or []

        for tree in seed_trees:
            if len(self.population) >= self.population_size:
                break
            strategy = Strategy(tree=deepcopy(tree))
            existing_exprs = {s.get_expr() for s in self.population}
            if strategy.get_expr() not in existing_exprs:
                self.population.append(strategy)

        if seed_trees:
            print(f"✓ Seeded {len(self.population)} champion strategies from vault (transfer learning active)")

        attempts = 0
        max_attempts = self.population_size * 10

        while len(self.population) < self.population_size and attempts < max_attempts:
            strategy = Strategy(tree=self.gp_tree.generate_random_tree(max_depth=4))
            existing_exprs = {s.get_expr() for s in self.population}
            if strategy.get_expr() not in existing_exprs:
                self.population.append(strategy)
            attempts += 1

        print(f"Created {len(self.population)} unique strategies")

    def evaluate_population(self, features: pd.DataFrame, market_returns: np.ndarray) -> None:
        print("Evaluating population...")

        for strategy in self.population:
            signal = TreeEvaluator.evaluate_tree(strategy.tree, features)
            position = SignalExecutor.signal_to_position(signal)
            position = SignalExecutor.apply_risk_controls(
                position,
                market_returns,
                mode=self.position_mode,
                max_exposure=self.max_exposure,
                target_vol=self.target_vol,
                vol_window=self.vol_window,
                annualization=self.annualization,
            )
            results = BacktestEngine.backtest_strategy(
                position,
                market_returns,
                annualization=self.annualization,
                initial_capital=self.initial_capital,
                drawdown_throttle=self.drawdown_throttle,
                throttle_exposure=self.throttle_exposure,
                calmar_weight=self.calmar_weight,
                return_weight=self.return_weight,
            )

            strategy.sharpe = results["sharpe"]
            strategy.calmar = results["calmar"]
            strategy.cagr = results["cagr"]
            strategy.drawdown = results["drawdown"]
            size = self.tree_size(strategy.tree)
            depth = self.tree_depth(strategy.tree)

            complexity_penalty = 0.0005 * size + 0.002 * depth

            strategy.fitness = results["fitness"] - complexity_penalty
            strategy.turnover = results["turnover"]
            strategy.final_equity = results["final_equity"]
            strategy.pnl = results["pnl"]
            strategy.total_return = results["total_return"]
            strategy.win_rate = results["win_rate"]

        self.population.sort(key=lambda s: s.fitness, reverse=True)

    def evolve_generation(self) -> List[Strategy]:
        print("Evolving next generation...")
        elite = self.population[: self.elite_size]
        print(f"Keeping {len(elite)} elite strategies")

        new_population = deepcopy(elite)
        while len(new_population) < self.population_size:
            parent = random.choice(elite)
            mutated_tree = self.gp_tree.mutate_tree(parent.tree, self.mutation_rate)
            mutated_strategy = Strategy(tree=mutated_tree)

            existing_exprs = {s.get_expr() for s in new_population}
            if mutated_strategy.get_expr() not in existing_exprs:
                new_population.append(mutated_strategy)

        self.population = new_population
        print(f"Created generation with {len(self.population)} strategies")
        return self.population

    def get_best_strategy(self) -> Optional[Strategy]:
        return self.population[0] if self.population else None

    def get_top_strategies(self, n: int = 5) -> List[Strategy]:
        return self.population[:n]


class WalkForwardEngine:
    """Walk-forward validation engine."""
    
    def __init__(self, window: int = 1000, step: int = 200):
        self.window = window
        self.step = step

    def split(self, data: pd.DataFrame) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
        splits = []
        for i in range(0, len(data) - self.window, self.step):
            train = data.iloc[i : i + self.window]
            test = data.iloc[i + self.window : i + self.window + self.step]
            if len(test) > 0:
                splits.append((train, test))
        return splits


class GPTradingEngine:
    """Main orchestrator for the GP trading research engine."""

    def __init__(
        self,
        symbol: str = "SPY",
        start_date: str = "2001-01-01",
        end_date: Optional[str] = None,
        data_interval: str = "1d",
        population_size: int = 50,
        num_generations: int = 20,
        initial_capital: float = 10_000,
        strategy_vault_path: Path = STRATEGY_VAULT_PATH,
        seed_from_vault: bool = True,
    ):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.data_interval = data_interval
        self.population_size = population_size
        self.num_generations = num_generations
        self.initial_capital = initial_capital
        self.strategy_vault_path = strategy_vault_path
        self.seed_from_vault = seed_from_vault

        self.data: Optional[pd.DataFrame] = None
        self.features: Optional[pd.DataFrame] = None
        self.evolution_engine: Optional[GeneticEvolutionEngine] = None

    @staticmethod
    def annualization_for_interval(interval: str) -> float:
        if interval == "1d":
            return 252
        if interval.endswith("m"):
            minutes = int(interval[:-1])
            return 252 * (390 / minutes)
        if interval.endswith("h"):
            hours = int(interval[:-1])
            return 252 * (6.5 / hours)
        return 252

    def run(self, run_number: int = 0) -> tuple[Strategy, list]:
        print("\n" + "=" * 70)
        print(f"VERSION 2 GP TRADING ENGINE - FIXED (Run {run_number})")
        print("=" * 70 + "\n")
        all_strategies = []

        # Show vault statistics
        if self.seed_from_vault:
            vault_stats = StrategyVault.get_vault_stats(self.strategy_vault_path)
            print(f"📚 Strategy Vault Status:")
            print(f"   Total strategies saved: {vault_stats['count']}")
            if vault_stats['count'] > 0:
                print(f"   Best fitness in vault: {vault_stats['best_fitness']:.4f}")
                print(f"   Average fitness (top 5): {vault_stats['top_5_avg']:.4f}")
                print(f"   → Transfer learning will leverage {min(10, vault_stats['count'])} champions\n")

        # Load data
        self.data = DataLayer.fetch_spy_data(
            symbol=self.symbol,
            start=self.start_date,
            end=self.end_date,
            interval=self.data_interval,
        )
        self.features = FeatureEngine.build_features(self.data)
        market_returns = self.data.loc[self.features.index, "returns"].values

        # Initialize evolution engine
        self.evolution_engine = GeneticEvolutionEngine(
            feature_names=self.features.columns.tolist(),
            population_size=self.population_size,
            annualization=self.annualization_for_interval(self.data_interval),
            initial_capital=self.initial_capital,
        )

        # Load seed strategies from vault
        seed_trees = []
        if self.seed_from_vault:
            seed_trees = StrategyVault.load_champions(
                self.features.columns.tolist(),
                path=self.strategy_vault_path,
                max_champions=min(10, self.population_size),
            )

        self.evolution_engine.initialize_population(seed_trees=seed_trees)

        print("\n" + "=" * 70)
        print("STARTING EVOLUTION WITH WALK-FORWARD VALIDATION")
        print("=" * 70 + "\n")

        # Walk-forward validation setup
        wf = WalkForwardEngine(window=1500, step=300)
        splits = wf.split(self.features)
        print(f"Walk-forward splits: {len(splits)}")

        for gen in range(self.num_generations):
            print(f"\n{'=' * 70}")
            print(f"GENERATION {gen + 1}/{self.num_generations}")
            print(f"{'=' * 70}")

            # Evaluate each strategy using walk-forward
            for strategy in self.evolution_engine.population:
                fitness_scores = []
                sharpe_scores = []
                calmar_scores = []

                for train_df, test_df in splits:
                    test_returns = self.data.loc[test_df.index, "returns"].values
                    
                    # Generate signal on test data
                    test_signal = TreeEvaluator.evaluate_tree(strategy.tree, test_df)
                    test_position = SignalExecutor.signal_to_position(test_signal)

                    # Ensure alignment
                    min_len = min(len(test_position), len(test_returns))
                    test_position = test_position[:min_len]
                    test_returns = test_returns[:min_len]

                    if len(test_position) < 10:
                        continue

                    # Check if strategy is actually trading
                    if np.mean(np.abs(test_position)) < 0.05:
                        fitness_scores.append(-1)
                        sharpe_scores.append(0)
                        calmar_scores.append(0)
                        continue

                    # Run backtest
                    results = BacktestEngine.backtest_strategy(
                        test_position,
                        test_returns,
                        annualization=self.annualization_for_interval(self.data_interval),
                        initial_capital=self.initial_capital,
                    )

                    if not results.get("invalid"):
                        fitness_scores.append(results["fitness"])
                        sharpe_scores.append(results["sharpe"])
                        calmar_scores.append(results["calmar"])

                if len(fitness_scores) == 0:
                    strategy.fitness = -999
                    strategy.sharpe = 0.0
                    strategy.calmar = 0.0
                    continue

                # Aggregate across walk-forward splits
                strategy.fitness = np.mean(fitness_scores)
                strategy.sharpe = np.median(sharpe_scores)
                strategy.calmar = np.median(calmar_scores)

                # Stability penalty (prevents overfit)
                strategy.fitness -= 0.1 * np.std(fitness_scores)

                if np.isnan(strategy.fitness) or strategy.fitness < -1:
                    strategy.fitness = -999

            # Sort population by fitness
            self.evolution_engine.population.sort(key=lambda s: s.fitness, reverse=True)
            all_strategies.append(deepcopy(self.evolution_engine.population))

            # Show top strategies
            print("\nTop 3 Strategies:")
            for i, strat in enumerate(self.evolution_engine.get_top_strategies(3), 1):
                print(
                    f"\n  #{i}: Fitness={strat.fitness:.4f} | "
                    f"Sharpe={strat.sharpe:.4f} | "
                    f"Calmar={strat.calmar:.4f}"
                )
                print(f"      Expression: {strat.get_expr()[:100]}...")

            # Evolve to next generation
            if gen < self.num_generations - 1:
                self.evolution_engine.evolve_generation()

        # Get best strategy and run full backtest
        best = self.evolution_engine.get_best_strategy()
        if best is None:
            raise RuntimeError("Evolution completed without producing a strategy.")

        # Run full backtest on best strategy
        signal = TreeEvaluator.evaluate_tree(best.tree, self.features)
        position = SignalExecutor.signal_to_position(signal)
        position = SignalExecutor.apply_risk_controls(
            position,
            market_returns,
            mode="long_short",
            max_exposure=1.0,
            annualization=self.annualization_for_interval(self.data_interval),
        )
        
        full_results = BacktestEngine.backtest_strategy(
            position,
            market_returns,
            annualization=self.annualization_for_interval(self.data_interval),
            initial_capital=self.initial_capital,
        )

        # Update best strategy with full results
        best.sharpe = full_results["sharpe"]
        best.calmar = full_results["calmar"]
        best.cagr = full_results["cagr"]
        best.drawdown = full_results["drawdown"]
        best.turnover = full_results["turnover"]
        best.final_equity = full_results["final_equity"]
        best.pnl = full_results["pnl"]
        best.total_return = full_results["total_return"]
        best.win_rate = full_results["win_rate"]

        print("\n" + "=" * 70)
        print("EVOLUTION COMPLETE")
        print("=" * 70 + "\n")
        print("BEST STRATEGY (Full Backtest):")
        print(f"   Fitness:  {best.fitness:.4f}")
        print(f"   Sharpe:   {best.sharpe:.4f}")
        print(f"   Calmar:   {best.calmar:.4f}")
        print(f"   CAGR:     {best.cagr:.4f}")
        print(f"   Drawdown: {best.drawdown:.4f}")
        print(f"   Turnover: {best.turnover:.4f}")
        print(f"   Start:    ${self.initial_capital:,.2f}")
        print(f"   End:      ${best.final_equity:,.2f}")
        print(f"   PnL:      ${best.pnl:,.2f}")
        print(f"   Return:   {best.total_return * 100:.2f}%")
        print(f"   Win Rate: {best.win_rate * 100:.2f}%")
        print("\n   Expression:")
        print(f"   {best.get_expr()}\n")

        # Save to vault
        StrategyVault.save_strategy(
            best,
            metadata={
                "symbol": self.symbol,
                "start_date": self.start_date,
                "end_date": self.end_date,
                "interval": self.data_interval,
                "population_size": self.population_size,
                "num_generations": self.num_generations,
                "initial_capital": self.initial_capital,
                "run_number": run_number,
            },
            path=self.strategy_vault_path,
        )
        print(f"✓ Saved best strategy to vault")

        # Run Monte Carlo simulation
        print("\n" + "=" * 70)
        print("MONTE CARLO ROBUSTNESS TESTING")
        print("=" * 70)
        
        mc_results = MonteCarloSimulator.run_simulation(
            strategy=best,
            features=self.features,
            market_returns=market_returns,
            n_simulations=1000,
            bootstrap=True,
            annualization=self.annualization_for_interval(self.data_interval),
            initial_capital=self.initial_capital,
        )
        
        print("\nMonte Carlo Results:")
        print(f"   Mean Final Equity:    ${mc_results['stats']['equity_mean']:,.2f}")
        print(f"   Median Final Equity:  ${mc_results['stats']['equity_median']:,.2f}")
        print(f"   5th Percentile:       ${mc_results['stats']['equity_5th']:,.2f}")
        print(f"   95th Percentile:      ${mc_results['stats']['equity_95th']:,.2f}")
        print(f"   Probability of Profit: {mc_results['stats']['prob_profit']*100:.1f}%")
        print(f"   Mean Sharpe:          {mc_results['stats']['sharpe_mean']:.4f}")
        print(f"   Median Return:        {mc_results['stats']['return_median']*100:.1f}%")
        
        # Save Monte Carlo plot
        mc_plot_path = Path(f"monte_carlo_run_{run_number}.png")
        MonteCarloSimulator.plot_monte_carlo_results(
            mc_results,
            strategy_name=f"Run {run_number}",
            save_path=mc_plot_path,
            initial_capital=self.initial_capital,
        )

        return best, all_strategies


if __name__ == "__main__":
    random.seed(42)
    np.random.seed(42)

    engine = GPTradingEngine(
        symbol="SPY",
        start_date="2001-01-01",
        end_date=None,
        data_interval="1d",
        population_size=30,
        num_generations=10,
        initial_capital=10_000,
    )

    print("\n" + "=" * 70)
    print("MULTI-RUN LEARNING EXPERIMENT")
    print("=" * 70)
    print("Each run will learn from previous champions in the vault...\n")

    best_overall = None
    best_score = -np.inf
    run_results = []
    all_runs_strategies = []

    # Run multiple experiments
    for i in range(1, 11):  # 10 runs
        print(f"\n{'#' * 70}")
        print(f"# STARTING RUN {i}/10")
        print(f"{'#' * 70}\n")
        
        best_strategy, run_strategies = engine.run(run_number=i)
        all_runs_strategies.extend(run_strategies)
        
        run_results.append({
            "run": i,
            "fitness": best_strategy.fitness,
            "sharpe": best_strategy.sharpe,
            "return": best_strategy.total_return,
            "pnl": best_strategy.pnl,
            "expression": best_strategy.get_expr()
        })

        if best_strategy.fitness > best_score:
            best_score = best_strategy.fitness
            best_overall = best_strategy
            print(f"\n🏆 NEW BEST OVERALL STRATEGY FOUND IN RUN {i}!")

    # Flatten all strategies
    flat_strategies = [
        strat
        for generation in all_runs_strategies
        for strat in generation
    ]

    print(f"\nTotal strategies collected: {len(flat_strategies)}")

    # Filter strategies
    flat_strategies = [
        s for s in flat_strategies
        if s.sharpe > 0.3 and s.drawdown > -0.7 and s.fitness > 0
    ]

    print(f"Filtered strategies (quality threshold): {len(flat_strategies)}")

    # Learning progression
    print("\n" + "=" * 70)
    print("LEARNING PROGRESSION ACROSS RUNS")
    print("=" * 70)
    for result in run_results:
        print(f"Run {result['run']:2d}: Fitness={result['fitness']:7.4f} | "
              f"Sharpe={result['sharpe']:6.4f} | Return={result['return']*100:6.2f}% | "
              f"PnL=${result['pnl']:,.2f}")

    # Best overall strategy
    print("\n" + "=" * 70)
    print("BEST STRATEGY ACROSS ALL RUNS")
    print("=" * 70)
    print(f"Fitness:  {best_overall.fitness:.4f}")
    print(f"Sharpe:   {best_overall.sharpe:.4f}")
    print(f"Calmar:   {best_overall.calmar:.4f}")
    print(f"CAGR:     {best_overall.cagr:.4f}")
    print(f"Drawdown: {best_overall.drawdown:.4f}")
    print(f"Turnover: {best_overall.turnover:.4f}")
    print(f"PnL:      ${best_overall.pnl:,.2f}")
    print(f"Return:   {best_overall.total_return * 100:.2f}%")
    print(f"Win Rate: {best_overall.win_rate * 100:.2f}%")
    print("\nExpression:")
    print(best_overall.get_expr())

    # Multi-strategy Monte Carlo
    if len(flat_strategies) > 0:
        print("\n" + "=" * 70)
        print("GLOBAL MULTI-STRATEGY MONTE CARLO")
        print("=" * 70)
        
        multi_mc = MonteCarloSimulator.run_multi_strategy_simulation(
            flat_strategies[:50],  # Use top 50 strategies
            engine.features,
            engine.data.loc[engine.features.index, "returns"].values,
            n_simulations=2000,
        )
        
        MonteCarloSimulator.plot_monte_carlo_results(
            {
                "final_equities": multi_mc["equity"],
                "sharpes": np.zeros(len(multi_mc["equity"])),
                "drawdowns": np.zeros(len(multi_mc["equity"])),
                "returns": multi_mc["returns"],
                "stats": {
                    "equity_mean": np.mean(multi_mc["equity"]),
                    "equity_median": np.median(multi_mc["equity"]),
                    "equity_5th": np.percentile(multi_mc["equity"], 5),
                    "equity_95th": np.percentile(multi_mc["equity"], 95),
                    "sharpe_mean": 0,
                    "sharpe_median": 0,
                    "return_mean": np.mean(multi_mc["returns"]),
                    "return_median": np.median(multi_mc["returns"]),
                    "prob_profit": np.mean(multi_mc["equity"] > 10000),
                }
            },
            strategy_name="GLOBAL MULTI-STRATEGY PORTFOLIO",
            save_path=Path("global_monte_carlo.png"),
            initial_capital=10000,
        )
        
        print("\nMULTI-STRATEGY MONTE CARLO RESULTS:")
        print(f"Mean Return:   {np.mean(multi_mc['returns']) * 100:.2f}%")
        print(f"Median Return: {np.median(multi_mc['returns']) * 100:.2f}%")
        print(f"Best Return:   {np.max(multi_mc['returns']) * 100:.2f}%")
        print(f"Worst Return:  {np.min(multi_mc['returns']) * 100:.2f}%")
        print(f"Prob Profit:   {np.mean(multi_mc['equity'] > 10000) * 100:.2f}%")

    # Final vault statistics
    final_vault_stats = StrategyVault.get_vault_stats()
    print("\n" + "=" * 70)
    print("FINAL STRATEGY VAULT KNOWLEDGE BASE")
    print("=" * 70)
    print(f"Total strategies discovered: {final_vault_stats['count']}")
    print(f"Best fitness achieved: {final_vault_stats['best_fitness']:.4f}")
    print(f"Top 5 average fitness: {final_vault_stats['top_5_avg']:.4f}")
    print("\n✓ Knowledge base will seed future runs for continuous improvement.")

    print("\n" + "=" * 70)
    print("Strategy discovery complete.")
    print("This is a research framework, not for live trading.")
    print("=" * 70)
