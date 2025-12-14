from state.state_manager import StateManager, JSONStateStore
from src.broker.paper_broker import PaperBroker
import os

def verify_atomic_execution():
    print("--- Verifying Atomic Execution ---")
    
    # 1. Setup Mock State
    store = JSONStateStore()
    manager = StateManager(store)
    
    # Clear state for test
    manager.state.open_positions = {}
    manager.state.daily_pnl = 0.0
    manager.save()
    
    broker = PaperBroker(manager, slippage_pct=0.0) # Zero slippage for easy math
    
    # 2. Test Entry (Atomic Write)
    print("\n[TEST 1] Place Order (Entry)")
    symbol = "NIFTY24DEC24500CE"
    qty = 50
    entry_price = 100.0
    sl = 90.0
    target = 120.0
    
    result = broker.place_order(
        symbol=symbol,
        quantity=qty,
        side="BUY",
        price=entry_price,
        stop_loss=sl,
        target=target,
        strategy_tag="TEST_STRATEGY",
        token=12345
    )
    
    print(f"Order Result: {result['status']} | ID: {result['order_id']}")
    
    # Verify State
    state = manager.get_state()
    if symbol in state['open_positions']:
        pos = state['open_positions'][symbol]
        print(f"✅ Position Found in State: {pos['symbol']}")
        
        # Verify Persistence of SL/Target
        if pos['stop_loss'] == sl and pos['target'] == target:
            print(f"✅ SL/Target Persisted: SL={pos['stop_loss']}, TGT={pos['target']}")
        else:
            print(f"❌ SL/Target Mismatch: {pos}")
    else:
        print("❌ Position NOT Found in State!")
        
    # 3. Test Exit (Atomic Write)
    print("\n[TEST 2] Close Position (Exit)")
    exit_price = 110.0
    
    close_result = broker.close_position(symbol, price=exit_price, reason="Test Exit")
    
    print(f"Close Result: {close_result['status']} | PnL: {close_result['net_pnl']}")
    
    # Verify State Cleared
    state = manager.get_state()
    if symbol not in state['open_positions']:
        print("✅ Position Removed from State")
    else:
        print(f"❌ Position Still ACTIVE: {state['open_positions']}")
        
    # Verify PnL Update
    # (110 - 100) * 50 = 500 Profit
    # Costs are non-zero in CostModel, so PnL should be < 500
    expected_gross = (exit_price - entry_price) * qty
    if state['daily_pnl'] > 0 and state['daily_pnl'] < expected_gross:
        print(f"✅ Daily PnL Updated Correctly: {state['daily_pnl']} (Gross: {expected_gross})")
    else:
        print(f"❌ Unexpected PnL: {state['daily_pnl']}")

if __name__ == "__main__":
    verify_atomic_execution()
