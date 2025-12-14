import logging

logger = logging.getLogger(__name__)

class CostModel:
    """
    NSE Options Cost Model (Updated for 2025).
    Used for estimating slippage and fees in Backtesting and Live execution.
    """
    
    # Fee Structure Constants
    BROKERAGE_PER_ORDER = 20.0
    STT_PERCENT_SELL = 0.001       # 0.1% on Sell Only (Increased Oct 2024)
    EXCHANGE_TXN_PERCENT = 0.0003503 # 0.03503% on Buy & Sell
    STAMP_DUTY_PERCENT_BUY = 0.00003 # 0.003% on Buy Only
    SEBI_TURNOVER_FEE = 0.000001   # ₹10 per crore
    GST_PERCENT = 0.18             # 18% on (Brokerage + Exchange + SEBI)

    @staticmethod
    def calculate_estimated_cost(entry_price: float, exit_price: float, quantity: int) -> float:
        """
        Calculates total round-trip cost (Buy + Sell).
        """
        turnover_buy = entry_price * quantity
        turnover_sell = exit_price * quantity
        
        # 1. Brokerage (Flat ₹20 per order)
        brokerage = CostModel.BROKERAGE_PER_ORDER * 2 
        
        # 2. STT (Security Transaction Tax) - SELL Side Only
        stt = turnover_sell * CostModel.STT_PERCENT_SELL
        
        # 3. Exchange Transaction Charges - Both Sides
        exchange_charges = (turnover_buy + turnover_sell) * CostModel.EXCHANGE_TXN_PERCENT
        
        # 4. Stamp Duty - BUY Side Only
        stamp_duty = turnover_buy * CostModel.STAMP_DUTY_PERCENT_BUY
        
        # 5. SEBI Turnover Fees - Both Sides
        sebi_fees = (turnover_buy + turnover_sell) * CostModel.SEBI_TURNOVER_FEE
        
        # 6. GST - 18% on Services (Brokerage + Exchange + SEBI)
        gst = (brokerage + exchange_charges + sebi_fees) * CostModel.GST_PERCENT
        
        total_tax_and_charges = brokerage + stt + exchange_charges + stamp_duty + sebi_fees + gst
        return total_tax_and_charges

    @staticmethod
    def estimate_breakeven_points(entry_price: float, quantity: int) -> float:
        """
        Returns the index points required to cover round-trip costs.
        Assuming Exit Price approx equals Entry Price for cost estimation.
        """
        # Estimate costs assuming breakeven (Exit = Entry)
        total_charges = CostModel.calculate_estimated_cost(entry_price, entry_price, quantity)
        
        # Points needed per unit
        points_needed = total_charges / quantity
        return points_needed
