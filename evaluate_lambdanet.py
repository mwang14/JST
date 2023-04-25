import sys
import json

if __name__ == "__main__":
    execution_results_file = sys.argv[1]
    lambdanet_results_file = sys.argv[2]
    with open(execution_results_file, 'r') as f:
        execution_results = json.load(f)
    with open(lambdanet_results_file, 'r') as f:
        lambdanet_results = f.read()
    executedLines = execution_results["executedLines"]
    variableMappings = execution_results["variableMappings"]

    
    for line in executedLines:
        script = line["scriptId"] + ".ts"
        line_number = line["line"] + 1 # lambdanet line numbers are 1-indexed so need to offset it
    lambdanet_parsed = lambdanet_results.split("=== File: ")
    print(lambdanet_parsed[2])
