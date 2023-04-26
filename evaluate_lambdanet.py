import sys
import json

def parse_lambdanet_line(lambdanet_line):
    filename = lambdanet_line.split('\n')[0].split(' ')[0]
    lines = lambdanet_line.split('\n')[1:]
    all_lines = []
    for info in lines:
        if not info:
            continue
        info = info.split(' ')
        line_info = info[0]
        start,end = line_info.split('-')
        start = eval(start)
        end = eval(end)
        end_line = end[0]
        all_lines.append(f"{filename} {end_line}")
    return all_lines

if __name__ == "__main__":
    execution_results_file = sys.argv[1]
    lambdanet_results_file = sys.argv[2]
    with open(execution_results_file, 'r') as f:
        execution_results = json.load(f)
    with open(lambdanet_results_file, 'r') as f:
        lambdanet_results = f.read()
    executedLines = execution_results["executedLines"]
    variableMappings = execution_results["variableMappings"]

    all_executed_lines = []
    for line in executedLines:
        script = line["scriptId"] + ".ts"
        line_number = line["line"] + 1 # lambdanet line numbers are 1-indexed so need to offset it
        all_executed_lines.append(f"{script} {line_number}")
    lambdanet_parsed = lambdanet_results.split("=== File: ")
    count = 0
    for line in lambdanet_parsed:
        if line:
            #print(line)
            all_lines = parse_lambdanet_line(line)
            for line in all_lines:
                if line in all_executed_lines:
                    count += 1
    print(count)
