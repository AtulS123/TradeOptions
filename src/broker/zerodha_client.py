import logging
import time
from kiteconnect import KiteConnect, exceptions
from typing import Dict, Any, List

from ..interfaces.broker import IVirtualBroker
from .cost_model import CostModel

logger = logging.getLogger(__name__)

class ZerodhaClient(IVirtualBroker):
    """
    Concrete Broker Implementation for Zerodha Kite Connect.
    Includes Strict Rate Limiting (Token Bucket) and Daily Safety Caps.
    """

    # Safety Constants
    MAX_ORDERS_PER_DAY = 1950
    RATE_LIMIT_DELAY = 0.34  # ~3 requests per second (1/3 = 0.33s, using 0.34 safety)
    
    def __init__(self, api_key: str, access_token: str):
        self.api_key = api_key
        self.access_token = access_token
        self.kite = KiteConnect(api_key=self.api_key)
        self.kite.set_access_token(self.access_token)
        
        self.daily_order_count = 0
        self.last_request_time = 0.0
        
        logger.info("ZerodhaClient Initialized.")

    def _wait_for_rate_limit(self):
        """
        Enforces 3 requests per second via blocking sleep.
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.RATE_LIMIT_DELAY:
            sleep_time = self.RATE_LIMIT_DELAY - time_since_last
            time.sleep(sleep_time)
            
        self.last_request_time = time.time()

    def authenticate(self):
        """
        Verifies connection.
        """
        try:
            self._wait_for_rate_limit()
            profile = self.kite.profile()
            logger.info(f"Authenticated as: {profile.get('user_name')}")
        except Exception as e:
            logger.error(f"Authentication Failed: {str(e)}")
            raise e

    def place_order(self, symbol: str, quantity: int, side: str, 
                   product: str, order_type: str, price: float = 0.0, 
                   trigger_price: float = 0.0) -> str:
        """
        Places a validation-checked order.
        """
        # 1. Safety Checks
        if self.daily_order_count >= self.MAX_ORDERS_PER_DAY:
            logger.critical("Daily Order Limit Reached (1950). Halting.")
            raise RuntimeError("Daily Order Limit Reached.")
            
        # NIFTY Lot Size Check (Hardcoded safety map for now, ideally dynamic)
        LOT_SIZE = 25
        if quantity % LOT_SIZE != 0:
            logger.warning(f"Quantity {quantity} is not multiple of lot size {LOT_SIZE}. Adjusting?")
            # For now, rejection or we proceed if user logic is trusted. Throwing warning.
        
        # 2. Estimate Cost
        estimated_cost = CostModel.calculate_estimated_cost(price, price, quantity)
        logger.info(f"Placing Order: {side} {quantity} {symbol} @ {price}. Est. Tax/Fees: ₹{estimated_cost:.2f}")

        # 3. Execution
        try:
            self._wait_for_rate_limit()
            
            # Map parameters to Kite constants
            transaction_type = self.kite.TRANSACTION_TYPE_BUY if side == "BUY" else self.kite.TRANSACTION_TYPE_SELL
            product_type = self.kite.PRODUCT_MIS if product == "MIS" else self.kite.PRODUCT_NRML
            kite_order_type = self.kite.ORDER_TYPE_MARKET if order_type == "MARKET" else self.kite.ORDER_TYPE_LIMIT
            
            order_id = self.kite.place_order(
                tradingsymbol=symbol,
                exchange=self.kite.EXCHANGE_NFO,
                transaction_type=transaction_type,
                quantity=quantity,
                variety=self.kite.VARIETY_REGULAR,
                order_type=kite_order_type,
                product=product_type,
                price=price if order_type == "LIMIT" else None,
                trigger_price=trigger_price if trigger_price > 0 else None
            )
            
            self.daily_order_count += 1
            logger.info(f"Order Placed. ID: {order_id}")
            return str(order_id)

        except exceptions.InputException as e:
            logger.error(f"Order Rejected (Input): {str(e)}")
            raise e
        except exceptions.NetworkException as e:
            logger.error(f"Order Failed (Network): {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"Order Error: {str(e)}")
            raise e

    def get_positions(self) -> List[Dict[str, Any]]:
        self._wait_for_rate_limit()
        return self.kite.positions()

    def get_limits(self) -> Dict[str, float]:
        self._wait_for_rate_limit()
        margins = self.kite.margins()
        return margins.get("equity", {})

    def cancel_order(self, order_id: str):
        self._wait_for_rate_limit()
        self.kite.cancel_order(variety=self.kite.VARIETY_REGULAR, order_id=order_id)
        logger.info(f"Order Cancelled: {order_id}")
