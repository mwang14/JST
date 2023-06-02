import sys
import json
import os

if __name__ == "__main__":
    results_path = sys.argv[1]
    out_dir = sys.argv[2]
    with open(results_path, 'r') as f:
        results = json.load(f)
    
    for i, result in enumerate(results):
        with open(os.path.join(out_dir, str(i)), 'w') as f:
            if "scope_results" in results_path:
                f.write(result["exists_outside"])
                f.write('\n\n')
            if "type_results" in results_path:
                f.write(result["type"])
                f.write('\n\n')
            f.write(result["prompt_info"]["prompt"])
        if i > 100:
            break