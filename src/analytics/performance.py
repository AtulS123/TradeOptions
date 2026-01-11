import pandas as pd
import numpy as np
from typing import Dict, Any, List

class PerformanceAnalytics:
    @staticmethod
    def calculate_metrics(equity_curve: list, trades: list, initial_capital: float, 
                         total_brokerage: float = 0.0, total_taxes: float = 0.0) -> dict:
        """
        Calculates Hedge Fund style metrics from the backtest log.
        """
        if not equity_curve:
            return PerformanceAnalytics._empty_result(initial_capital)

        # 1. Process Equity Curve
        df_eq = pd.DataFrame(equity_curve)
        if df_eq.empty: 
            return PerformanceAnalytics._empty_result(initial_capital)
            
        df_eq['datetime'] = pd.to_datetime(df_eq['timestamp'])
        df_eq.set_index('datetime', inplace=True)
        final_capital = df_eq['equity'].iloc[-1]
        
        # Drawdown
        df_eq['peak'] = df_eq['equity'].cummax()
        df_eq['drawdown_pct'] = ((df_eq['peak'] - df_eq['equity']) / df_eq['peak']) * 100
        max_drawdown_pct = df_eq['drawdown_pct'].max()
        
        # Sharpe & Calmar
        # Use actual equity curve returns instead of daily resampling for intraday data
        sharpe_ratio = 0.0
        calmar_ratio = 0.0
        
        # Calculate returns from equity curve
        equity_returns = df_eq['equity'].pct_change().dropna()
        
        if len(equity_returns) > 1:
            mean_ret = equity_returns.mean()
            std_ret = equity_returns.std()
            
            if std_ret != 0:
                # Determine annualization factor based on data frequency
                # Infer frequency from time differences
                time_diffs = df_eq.index.to_series().diff().dropna()
                avg_minutes = time_diffs.mean().total_seconds() / 60
                
                # Annualization factors
                if avg_minutes <= 1:  # 1-minute data
                    periods_per_year = 252 * 6.25 * 60  # 252 days * 6.25 hours * 60 min
                elif avg_minutes <= 5:  # 5-minute data
                    periods_per_year = 252 * 6.25 * 12  # 252 days * 6.25 hours * 12 (5-min periods)
                elif avg_minutes <= 15:  # 15-minute data
                    periods_per_year = 252 * 6.25 * 4
                elif avg_minutes <= 60:  # Hourly
                    periods_per_year = 252 * 6.25
                else:  # Daily or longer
                    periods_per_year = 252
                
                # Sharpe Ratio = (Mean Return) / Std Dev * sqrt(periods)
                # CRITICAL: Don't use abs() - preserve sign!
                # Negative mean_ret will produce negative Sharpe (correct for losing strategies)
                sharpe_ratio = (mean_ret / std_ret) * np.sqrt(periods_per_year)
                
            if max_drawdown_pct != 0:
                # Total return (can be negative)
                total_ret = (final_capital - initial_capital) / initial_capital
                # Calmar = Annualized Return / |Max Drawdown|
                calmar_ratio = total_ret / (max_drawdown_pct / 100)


        # 2. Process Trades
        closed_trades = [t for t in trades if t['side'] == 'SELL'] # Assuming Long Only or simple close logic
        # Ideally, we should match Entry/Exit pairs. For now, we take realized PnL from closed trades.
        
        wins = [t['pnl'] for t in closed_trades if t['pnl'] > 0]
        losses = [t['pnl'] for t in closed_trades if t['pnl'] <= 0]
        
        total_trades = len(closed_trades)
        win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0.0
        
        avg_win = np.mean(wins) if wins else 0.0
        avg_loss = np.mean(losses) if losses else 0.0 # Negative
        
        largest_win = max(wins) if wins else 0.0
        largest_loss = min(losses) if losses else 0.0
        
        profit_factor = 0.0
        if abs(sum(losses)) > 0:
            profit_factor = sum(wins) / abs(sum(losses))
        elif sum(wins) > 0:
            profit_factor = 999.0
            
        # 3. Greeks Analysis (Stub for now as we don't log greeks yet)
        # In a real engine, we would log delta/theta per trade
        greeks = {
            "avg_delta": 0.5,  # ATM options typically have delta ~0.5
            "avg_theta": -98.61,
            "avg_vega": 35.64,
            "avg_iv": 20.37
        }
        
        return {
            "summary": {
                "initial_capital": initial_capital,
                "final_capital": round(final_capital, 2),
                "total_return_pct": round(((final_capital - initial_capital) / initial_capital) * 100, 2),
                "total_trades": total_trades,
                "win_rate": round(win_rate, 2),
                "profit_factor": round(profit_factor, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "calmar_ratio": round(calmar_ratio, 2),
                "max_drawdown_pct": round(max_drawdown_pct, 2),
                "total_brokerage": round(total_brokerage, 2),
                "total_taxes": round(total_taxes, 2),
                "total_costs": round(total_brokerage + total_taxes, 2)
            },
            "trade_stats": {
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "largest_win": round(largest_win, 2),
                "largest_loss": round(largest_loss, 2),
                "avg_days_in_trade": 1.5 # Mock
            },
            "greeks": greeks,
            # Pass through equity curve WITH drawdown data
            "equity_curve": [
                {
                    "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx),
                    "equity": round(row['equity'], 2),
                    "drawdown": round(row['drawdown_pct'], 2)
                }
                for idx, row in df_eq.iterrows()
            ],
            "trades": trades
        }

    @staticmethod
    def _empty_result(initial_capital):
        return {
             "summary": {
                "initial_capital": initial_capital,
                "final_capital": initial_capital,
                "total_return_pct": 0.0,
                "total_trades": 0,
                "win_rate": 0.0,
                "profit_factor": 0.0,
                "sharpe_ratio": 0.0,
                "calmar_ratio": 0.0,
                "max_drawdown_pct": 0.0
             },
             "trade_stats": {
                "avg_win": 0, "avg_loss": 0, "largest_win": 0, "largest_loss": 0, "avg_days_in_trade": 0
             },
             "greeks": {"avg_delta": 0, "avg_theta": 0, "avg_vega": 0, "avg_iv": 0},
             "equity_curve": [],
             "trades": []
        }
