import glob
import sys
import esprima
import os
import json
import tqdm
import jsbeautifier

function_count = 0
total_lines = 0
total_files = 0
total_lines_executed = 0
def functionCount(node, meta):
    global function_count
    if node.type == "FunctionExpression":
        function_count += 1

def get_javascript_files(data_dir):
    result = []
    for filename in os.listdir(data_dir):
        if filename.isdigit():
            result.append(os.path.join(data_dir,filename))
    return result

def get_beautifier_opts():
    opts = jsbeautifier.default_options
    opts.space_in_empty_paren = False
    opts.space_in_paren = False
    opts.space_after_anon_function = False
    opts.space_after_named_function = False
    opts.indent_size = 4
    return opts

def beautify_all_files(in_dir):
    opts = get_beautifier_opts()
    for website_dir in os.listdir(in_dir):
        website_dir = os.path.join(in_dir, website_dir)
        if os.path.exists(os.path.join(website_dir, "beautified")):
            continue
        os.makedirs(os.path.join(website_dir, "beautified"), exist_ok=True)
        javascript_files = get_javascript_files(website_dir)
        for javascript_file in javascript_files:
            try:
                js_content_beautified = jsbeautifier.beautify_file(javascript_file, opts)
                with open(os.path.join(website_dir, "beautified", f"{os.path.basename(javascript_file)}.ts"), 'w') as f:
                    f.write(js_content_beautified)
            except Exception:
                continue
        print(f"beautified {website_dir}")
if __name__ == "__main__":
    extracted_dir = sys.argv[1]

    beautify_all_files(extracted_dir)

    path = os.path.join(f"{extracted_dir}", "**/beautified/*.ts")
    
    all_lines = set()
    all_files = set()
    for js_file in tqdm.tqdm(glob.glob(path, recursive=True)):
        with open(js_file, 'r') as f:
            js_content = f.read()
        js_content_hash = hash(js_content)
        all_files.add(js_content_hash)
        lines = js_content.split('\n')
        for line in lines:
            all_lines.add(hash(line))

       
    
    new_data_files = os.path.join(f"{extracted_dir}", "**/data.json")
    for data_file in tqdm.tqdm(glob.glob(new_data_files, recursive=True)):
        with open(data_file, 'r') as f:
            raw_data = f.read()
            if len(raw_data):
                execution_data = json.loads(raw_data)
            else:
                continue
        total_lines_executed += len(execution_data["executedLines"])

    print(f"statements executed: {total_lines_executed}")
    print(f"total number of lines: {len(all_lines)}")
    print(f"total number of files: {len(all_files)}")

    with open("result.txt", 'w') as f:
        f.write(f"{total_lines_executed} {len(all_lines)} {len(all_files)}")

    