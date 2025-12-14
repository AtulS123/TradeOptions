from typing import List, Dict, Optional, Union

def get_best_strike(chain_data: List[Dict], option_type: str, target_delta: float) -> Optional[Dict]:
    """
    Selects the optimal strike based on target Delta.
    
    Args:
        chain_data: List of dicts representing the option chain.
        option_type: "CE" or "PE"
        target_delta: Target Delta (e.g., 0.5 or -0.5)
        
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
            token = row.get('ce_token') # Ensure main.py adds this
        elif option_type == "PE":
            delta = row.get('putDelta')
            ltp = row.get('putLTP')
            token = row.get('pe_token') # Ensure main.py adds this
        else:
            continue
            
        if delta is None or ltp is None or token is None:
            continue
            
        # Delta Matching Logic
        # Calculate absolute difference
        diff = abs(delta - target_delta)
        
        if diff < min_diff:
            min_diff = diff
            best_match = {
                "strike": strike,
                "instrument_token": token,
                "ltp": ltp,
                "delta": delta,
                "type": option_type
            }
            
    if best_match and min_diff <= MAX_DELTA_DIFF:
        return best_match
        
    return None
