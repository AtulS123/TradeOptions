try:
    import numpy
    print("Numpy imported successfully")
except ImportError as e:
    print(f"Numpy failed: {e}")

try:
    import pandas
    print("Pandas imported successfully")
except ImportError as e:
    print(f"Pandas failed: {e}")
