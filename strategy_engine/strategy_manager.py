from typing import List, Optional
from .strategies.base import BaseStrategy

class StrategyManager:
    """
    The Orchestrator.
    Routes ticks to registered strategies and collects signals.
    """
    
    def __init__(self):
        self.strategies: List[BaseStrategy] = []
        
    def register_strategy(self, strategy: BaseStrategy):
        """Adds a strategy to the active list."""
        self.strategies.append(strategy)
        print(f"Strategy Registered: {strategy.name}")

    def on_tick(self, tick: dict) -> List[dict]:
        """
        Passes tick to all strategies.
        Returns aggregated list of signals.
        """
        signals = []
        for strategy in self.strategies:
            try:
                sig = strategy.process_tick(tick)
                if sig:
                    signals.append(sig)
            except Exception as e:
                print(f"Error in strategy {strategy.name}: {e}")
                
        return signals

    def restore_positions(self, open_positions: dict):
        """
        Restores active positions to strategies (rehydration).
        """
        # For now, simply log it. In a real system, we might route these to strategies.
        count = len(open_positions)
        if count > 0:
            print(f"StrategyManager: Rehydrated {count} active positions.")
            # TODO: Implement granular rehydration if strategies maintain their own list
            # for strategy in self.strategies:
            #     if hasattr(strategy, 'restore_position'): ...

    def force_exit(self, token: int):
        """
        Manual override to force exit a position.
        """
        print(f"StrategyManager: Force Exit triggered for token {token}")
        # Notify strategies if they track this state
