import logging

logger = logging.getLogger(__name__)

class CostModel:
    """
    NSE Options Cost Model (Updated for 2025).
    Used for estimating slippage and fees in Backtesting and Live execution.
    """
    
    # Fee Structure Constants (Zerodha / NSE - Updated Oct 2024)
    BROKERAGE_PER_ORDER = 20.0
    STT_PERCENT_SELL = 0.001       # 0.1% on Sell Only (Premium)
    EXCHANGE_TXN_PERCENT = 0.00035 # 0.035% (NSE Options)
    STAMP_DUTY_PERCENT_BUY = 0.00003 # 0.003% on Buy Only
    SEBI_TURNOVER_FEE = 0.0000015  # ₹15 per crore
    GST_PERCENT = 0.18             # 18% on (Brokerage + Txn + SEBI)

    @staticmethod
    def get_breakdown(price: float, quantity: int, side: str) -> dict:
        """
        Calculates granular cost breakdown for a SINGLE leg.
        """
        turnover = price * quantity
        
        # 1. Brokerage
        brokerage = CostModel.BROKERAGE_PER_ORDER
        
        # 2. STT (Sell Side Only)
        stt = 0.0
        if side == "SELL":
            stt = turnover * CostModel.STT_PERCENT_SELL
            
        # 3. Exchange Txn
        exchange_charges = turnover * CostModel.EXCHANGE_TXN_PERCENT
        
        # 4. Stamp Duty (Buy Side Only)
        stamp_duty = 0.0
        if side == "BUY":
            stamp_duty = turnover * CostModel.STAMP_DUTY_PERCENT_BUY
            
        # 5. SEBI
        sebi_fees = turnover * CostModel.SEBI_TURNOVER_FEE
        
        # 6. GST
        gst = (brokerage + exchange_charges + sebi_fees) * CostModel.GST_PERCENT
        
        total = brokerage + stt + exchange_charges + stamp_duty + sebi_fees + gst
        
        return {
            "brokerage": brokerage,
            "stt": stt,
            "exchange_charges": exchange_charges,
            "stamp_duty": stamp_duty,
            "sebi_fees": sebi_fees,
            "gst": gst,
            "total": round(total, 2)
        }

    @staticmethod
    def calculate_transaction_cost(price: float, quantity: int, side: str) -> float:
        """
        Calculates total cost for a SINGLE leg (Buy OR Sell).
        """
        breakdown = CostModel.get_breakdown(price, quantity, side)
        return breakdown["total"]

    @staticmethod
    def calculate_estimated_cost(entry_price: float, exit_price: float, quantity: int) -> float:
        """
        Legacy wrapper for Round-Trip estimation.
        """
        buy_cost = CostModel.calculate_transaction_cost(entry_price, quantity, "BUY")
        sell_cost = CostModel.calculate_transaction_cost(exit_price, quantity, "SELL")
        return buy_cost + sell_cost
