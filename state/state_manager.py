import json
import logging
import os
from datetime import datetime, date
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

@dataclass
class TradeState:
    """
    Data structure representing the persistent state of the trading bot.
    """
    daily_pnl: float = 0.0
    kill_switch_active: bool = False
    open_positions: Dict[str, dict] = field(default_factory=dict)
    orders: List[dict] = field(default_factory=list) # Log of all orders (Open/Executed/Cancelled)
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())

class BaseStateStore(ABC):
    @abstractmethod
    def save(self, state: TradeState):
        pass

    @abstractmethod
    def load(self) -> TradeState:
        pass

    @abstractmethod
    def clear(self):
        pass

class JSONStateStore(BaseStateStore):
    def __init__(self, filepath: str = "trading_state.json"):
        self.filepath = filepath

    def save(self, state: TradeState):
        try:
            state.last_updated = datetime.now().isoformat()
            data = asdict(state)
            # Create tmp file then rename to avoid corruption on write interrupt
            tmp_path = self.filepath + ".tmp"
            with open(tmp_path, 'w') as f:
                json.dump(data, f, indent=4)
            
            if os.path.exists(self.filepath):
                os.remove(self.filepath)
            os.rename(tmp_path, self.filepath)
            
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load(self) -> TradeState:
        if not os.path.exists(self.filepath):
            return TradeState()

        try:
            with open(self.filepath, 'r') as f:
                data = json.load(f)
                
            # Date Check for Daily Reset
            last_updated = datetime.fromisoformat(data.get('last_updated', datetime.now().isoformat()))
            if last_updated.date() < date.today():
                logger.info("New Day detected. Resetting Daily PnL and State.")
                return TradeState() # Fresh state
                
            return TradeState(**data)

        except json.JSONDecodeError:
            logger.critical("State File Corrupted! Starting with fresh state.")
            return TradeState() # Corruption Recovery
        except Exception as e:
            logger.error(f"Error loading state: {e}")
            return TradeState()

    def clear(self):
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

class StateManager:
    """
    Manages the active state and syncs with the store.
    """
    def __init__(self, store: BaseStateStore):
        self.store = store
        self.state = TradeState()
        
    def load(self):
        self.state = self.store.load()
        return self.state
        
    def save(self):
        self.store.save(self.state)
        
    def get_state(self) -> dict:
        return asdict(self.state)
        
    def update_pnl(self, pnl: float):
        self.state.daily_pnl += pnl
        self.save()
        
    def set_kill_switch(self, active: bool):
        self.state.kill_switch_active = active
        self.save()
        
    def add_position(self, symbol: str, details: dict):
        self.state.open_positions[symbol] = details
        self.save()
        
    def close_position(self, symbol: str):
        if symbol in self.state.open_positions:
            del self.state.open_positions[symbol]
            self.save()
            
    def add_order(self, order: dict):
        """Appends an order to the order log."""
        self.state.orders.append(order)
        self.save()

    def get_active_tokens(self) -> List[int]:
        """Returns list of active instrument tokens (as ints)."""
        # Assuming keys are stringified tokens or dict has 'token' field.
        # If keys are symbols, we need to inspect the value dict for 'token'.
        tokens = []
        for key, details in self.state.open_positions.items():
            # Try to get token from details, fallback to key if it looks like an int
            t = details.get('token')
            if t:
                tokens.append(int(t))
        return tokens
