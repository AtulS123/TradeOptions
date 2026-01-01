from typing import List, Dict, Optional, Union

def get_best_strike(chain_data: List[Dict], option_type: str, target_delta: float, min_oi: int = 500) -> Optional[Dict]:
    """
    Selects the optimal strike based on target Delta.
    
    Args:
        chain_data: List of dicts representing the option chain.
        option_type: "CE" or "PE"
        target_delta: Target Delta (e.g., 0.5 or -0.5)
        min_oi: Minimum Open Interest required to consider a strike (default 500).
        
    Returns:
        Dict containing strike details or None if no suitable match found.
    """
    if not chain_data:
        return None
        
    best_match = None
    min_diff = 1.0
    
    # Safety Threshold: If closest strike is > 0.15 Delta away, reject it.
    MAX_DELTA_DIFF = 0.15
    
    for row in chain_data:
        strike = row.get('strike')
        
        if option_type == "CE":
            delta = row.get('callDelta')
            ltp = row.get('callLTP')
            token = row.get('ce_token')
            oi = row.get('callOI', 0)
            volume = row.get('callVolume', 0)
        elif option_type == "PE":
            delta = row.get('putDelta')
            ltp = row.get('putLTP')
            token = row.get('pe_token')
            oi = row.get('putOI', 0)
            volume = row.get('putVolume', 0)
        else:
            continue
            
        # 1. Safety Guard: Check for None or missing data
        if delta is None or ltp is None or token is None:
            continue
            
        # 2. Liquidity Guard: Check if Strike is Liquid
        if oi < min_oi and volume == 0:
            # If no OI and no Volume, it's a ghost strike. Skip.
            continue

        # Delta Matching Logic
        diff = abs(delta - target_delta)
        
        if diff < min_diff:
            min_diff = diff
            best_match = {
                "strike": strike,
                "token": token,
                "instrument_token": token,
                "ltp": ltp,
                "delta": delta,
                "type": option_type,
                "oi": oi,
                "volume": volume,
                "symbol": row.get('callSymbol') if option_type == "CE" else row.get('putSymbol')
            }
            
    if best_match and min_diff <= MAX_DELTA_DIFF:
        return best_match
        
    return None
