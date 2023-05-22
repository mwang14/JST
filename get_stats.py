import glob
import sys
import esprima
import os
import json
import tqdm

function_count = 0
total_lines = 0
total_files = 0
total_lines_executed = 0
def functionCount(node, meta):
    global function_count
    if node.type == "FunctionExpression":
        function_count += 1


if __name__ == "__main__":
    extracted_dir = sys.argv[1]

    path = os.path.join(f"{extracted_dir}", "**/beautified/*.ts")
    
    for js_file in tqdm.tqdm(glob.glob(path, recursive=True)):
        with open(js_file, 'r') as f:
            js_content = f.read()
        try:
            esprima.parseScript(js_content, {}, functionCount)
        except Exception:
            continue
        total_lines += len(js_content.split('\n'))
        total_files += 1
    
    
    new_data_files = os.path.join(f"{extracted_dir}", "**/new_data.json")
    for data_file in tqdm.tqdm(glob.glob(new_data_files, recursive=True)):
        with open(data_file, 'r') as f:
            raw_data = f.read()
            if len(raw_data):
                execution_data = json.loads(raw_data)
            else:
                continue
        total_lines_executed += len(execution_data["executedLines"])
    print(f"statements executed: {total_lines_executed}")
    print(f"number of functions: {function_count}")
    print(f"total number of lines: {total_lines}")
    print(f"total number of files: {total_files}")

    with open("result.txt", 'w') as f:
        f.write(f"{total_lines_executed} {function_count} {total_lines} {total_files}")

    