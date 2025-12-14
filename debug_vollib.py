try:
    import py_vollib
    from py_vollib.black_scholes.implied_volatility import implied_volatility
    print("py_vollib imported successfully")
except Exception as e:
    print(f"py_vollib failed: {e}")
except ImportError as e:
    print(f"py_vollib import error: {e}")
