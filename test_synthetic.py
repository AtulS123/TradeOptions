import pandas as pd
import sys
import os
sys.path.append(os.getcwd())
try:
    from src.utils.synthetic import generate_synthetic_feed
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

def test_syn():
    print("Testing generate_synthetic_feed...")
    try:
        spot_df = pd.read_csv("test_spot_verify.csv")
        vix_df = pd.read_csv("test_vix_verify.csv")
        
        df = generate_synthetic_feed(spot_df, vix_df)
        print("Columns:", df.columns)
        print("Rows:", len(df))
        if 'call_price' in df.columns:
            print("Success! call_price found.")
        else:
            print("Failure! call_price missing.")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_syn()
