import sys
import json
import os
import shutil

def parse_lambdanet_line(lambdanet_line):
    filename = lambdanet_line.split('\n')[0].split(' ')[0].split('_')[1]
    lines = lambdanet_line.split('\n')[1:]
    result = {}
    for info in lines:
        if not info:
            continue
        info = info.split(' ')
        line_info = info[0]
        start,end = line_info.split('-')
        start = eval(start)
        end = eval(end)
        end_line = end[0]
        
        line_info = {}
        
        variable_name = info[1].replace("'", "").replace(':', '')
        key = f"{end_line} {variable_name}"
        types = info[2:]
        types_indices = [1,3,5,7,9]
        types = [types[i] for i in types_indices]
        types = [type.replace(',','').lower() for type in types]
        line_info["variable_name"] = variable_name
        line_info["types"] = types
        result[key] = types
    return result


def copy_chatgpt_files(types_results_file, out_directory):
    with open(types_results_file, 'r') as f:
        types_results = json.load(f)
    filepaths = []
    for result in types_results:
        path = result["prompt_info"]["path"]
        script_id = result["prompt_info"]["scriptId"]
        filename = os.path.join(path, "beautified", f"{script_id}.ts")
        website = os.path.basename(path)
        out_file = os.path.join(out_directory, f"{website}_{script_id}.ts")
        print(f"copying {filename} to {out_file}")
        shutil.copy2(filename, out_file)

def get_chatgpt_files(types_results_file):
    with open(types_results_file, 'r') as f:
        types_results = json.load(f)
    results = []
    for result in types_results:
        info = {}
        path = result["prompt_info"]["path"]
        script_id = result["prompt_info"]["scriptId"]
        website = os.path.basename(path)
        script_id = f"{script_id}.ts"
        variable_name = result["prompt_info"]["prompt"].split(' ')[11]
        line = result["prompt_info"]["line"]
        real_type = result["type"]
        info["website"] = website
        info["scriptId"] = script_id
        info["variable_name"] = variable_name.replace("'",'')
        info["line"] = line
        info["type"] = real_type
        results.append(info)
    return results

def get_lambdanet_results_for_script(lambdanet_results_dir, website, script_id):
    lambdanet_results_file = os.path.join(lambdanet_results_dir, website)
    if not os.path.exists(lambdanet_results_file):
        return None
    with open(lambdanet_results_file, 'r') as f:
        lambdanet_results = f.read()
    lambdanet_parsed = lambdanet_results.split("=== File: ")
    for lambdanet_line in lambdanet_parsed:
        if not lambdanet_line:
            continue
        lambdanet_script_id = lambdanet_line.split('\n')[0].split(' ')[0].split('_')[1]
        if lambdanet_script_id == script_id:
            lambdanet_results_for_script_id = parse_lambdanet_line(lambdanet_line)
            return lambdanet_results_for_script_id


if __name__ == "__main__":
    types_results_file = sys.argv[1]
    lambdanet_results_dir = sys.argv[2]
    ground_truth = get_chatgpt_files(types_results_file)
    for info in ground_truth:
        website = info["website"]
        script_id = info["scriptId"]
        var_name = info["variable_name"]
        line = info["line"]
        ground_truth = info["type"]
        lambdanet_results_for_script = get_lambdanet_results_for_script(lambdanet_results_dir, website, script_id)
        if not lambdanet_results_for_script:
            continue
        key = f"{line} {var_name}"
        if key in lambdanet_results_for_script:
            print(ground_truth, lambdanet_results_for_script[key], website, script_id, var_name, line)
        

