from datetime import datetime, time, date

# NSE Holidays 2024-2025 (Partial List - maintain this!)
# Format: "YYYY-MM-DD"
NSE_HOLIDAYS = {
    "2024-01-22", # Special Holiday
    "2024-01-26", # Republic Day
    "2024-03-08", # Mahashivratri
    "2024-03-25", # Holi
    "2024-03-29", # Good Friday
    "2024-04-11", # Id-Ul-Fitr
    "2024-04-17", # Ram Navami
    "2024-05-01", # Maharashtra Day
    "2024-06-17", # Bakri Id
    "2024-07-17", # Moharram
    "2024-08-15", # Independence Day
    "2024-10-02", # Gandhi Jayanti
    "2024-11-01", # Diwali
    "2024-11-15", # Gurunanak Jayanti
    "2024-12-25", # Christmas
    
    # 2025 (Projected/Key dates - update as official circulars come)
    "2025-01-26", # Republic Day
    "2025-02-26", # Mahashivratri (Tentative)
    "2025-03-14", # Holi (Tentative)
    "2025-08-15", # Independence Day
    "2025-10-02", # Gandhi Jayanti
    "2025-10-20", # Diwali (Tentative)
    "2025-12-25", # Christmas
    
    # 2026 (Projected)
    "2026-01-26", # Republic Day
    "2026-04-03", # Good Friday
    "2026-04-14", # Dr. Ambedkar Jayanti
    "2026-05-01", # Maharashtra Day
    "2026-08-15", # Independence Day
    "2026-10-02", # Gandhi Jayanti
    "2026-12-25", # Christmas
}

MARKET_START = time(9, 15)
MARKET_END = time(15, 30)

def is_market_open() -> bool:
    """
    Checks if the Indian Equity Market is currently open.
    Rules:
    1. Weekday (Mon-Fri)
    2. Time: 09:15 - 15:30 IST
    3. Not a Holiday
    """
    now = datetime.now() # Assumes Server is running in IST or user wants System Time
    current_date = now.date()
    current_time = now.time()
    
    # Check 1: Weekend
    if current_date.weekday() > 4: # 5=Sat, 6=Sun
        return False
        
    # Check 2: Holidays
    if str(current_date) in NSE_HOLIDAYS:
        return False
        
    # Check 3: Time
    if current_time >= MARKET_START and current_time <= MARKET_END:
        return True
        
    return False

def get_market_state_label() -> str:
    """Returns 'Open' or 'Closed' for UI display"""
    return "Open" if is_market_open() else "Closed"
