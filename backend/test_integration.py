import sys
from pathlib import Path
import pandas as pd

# Add the backend to sys.path so we can import services
backend_path = Path("/home/yannick/Code/hack-nation/backend")
sys.path.append(str(backend_path))

from services.prediction_service import prediction_service

def test_integration():
    # Provide a mock feature dictionary
    example_row = {
        "gene_aac(3)-IId": 0,
        "mut_gyrA_S83L": 1,
        "gene_bla": 1,
        "gene_dfrA": 1
    }

    
    # Remove metadata features that prediction_service will ignore anyway, just to simulate Pipeline 1's output
    # (actually prediction_service ignores them, but let's test the whole thing)
    
    print("Testing integration...")
    results = prediction_service.predict(example_row)
    
    if isinstance(results, dict) and "error" in results:
        print(f"Integration failed: {results['error']}")
        return

    import json
    print(json.dumps(results, indent=2))
    
    print("\nConfirmation:")
    print("- Backend prediction service wrapper returned successfully.")
    print(f"- Number of antibiotics scored: {len(results)}")
    print("- 'no_call' field is present: ", all('no_call' in res for res in results))

if __name__ == "__main__":
    test_integration()
