import json
import argparse
import glob
import os
import hashlib
import sys
import tiktoken
import base64
import random
import esprima
import pandas as pd
import gen_datasets

def get_type(var_info):
    if "className" in var_info:
        return var_info["className"]
    elif "subtype" in var_info:
        return var_info["subtype"]
    else: 
        return var_info["type"]

def get_type_info(data_json, scripts_tokenized):
    execution_info = data_json["variableMappings"]
    lines_executed = data_json["executedLines"]
    result = {} 
    for i,info in enumerate(execution_info):
        for var_name in info:
            var_result = {}
            var_info = info[var_name]
            var_type = get_type(var_info)
            scope = var_info["scopeInfo"]
            if var_type == "function" or var_type == "undefined" or scope["scope"] == "global":
                continue
            start_line = scope["startLocation"]["lineNumber"]
            end_line = scope["endLocation"]["lineNumber"]
            real_var_name = '_'.join(var_name.split('_')[:-1])
            script_id = scope["startLocation"]["scriptId"]
            if script_id in scripts_tokenized:
                var_definition_line = gen_datasets.get_variable_definition_line(scripts_tokenized[script_id], real_var_name, start_line, end_line)
                if var_definition_line:
                    var_result["line"] = var_definition_line
                    var_result["type"] = var_type
                    var_result["script_id"] = script_id
                    var_result["scope_start_line"] = start_line
                    var_result["scope_end_line"] = end_line
                    result[var_name] = var_result
    return result


def gen_type_prompt(code_snippet, var_name, line):
    return f"What are the top 5 most likely types for the variable '{var_name}' defined on line {line}? \n\n ```\n{code_snippet}\n```"

def gen_type_prompts(type_info, scripts_json, path):
    result = []
    for var_name, var_info in type_info.items():
        var_result = {}
        script_id = var_info["script_id"]
        line = var_info["line"]
        scope_start_line = var_info["scope_start_line"]
        scope_end_line = var_info["scope_end_line"]
        script_contents = scripts_json[script_id].split('\n')
        code_snippet = gen_datasets.get_script_contents_between_scope(script_contents, scope_start_line, scope_end_line)
        if code_snippet:
            adjusted_line = line - scope_start_line
            real_var_name = '_'.join(var_name.split('_')[:-1])
            prompt = gen_type_prompt(code_snippet, real_var_name, adjusted_line)
            var_result["prompt"] = prompt
            var_result["type"] = var_info["type"]
            var_result["path"] = path
            var_result["scriptId"] = script_id
            var_result["line"] = line
            result.append(var_result)
    return result

if __name__ == "__main__":
    extracted_dir = sys.argv[1]
    data_json_files = glob.glob(os.path.join(extracted_dir, "**/new_data.json"), recursive=True)
    for data_json_file in data_json_files:
        print(f"running on {data_json_file}")
        out_dir = os.path.dirname(data_json_file)
        with open(data_json_file, 'r') as f:
            try:
                data_json = json.load(f)
            except json.decoder.JSONDecodeError:
                continue
        unique_id_file = os.path.join(out_dir, "unique_ids.json")
        if os.path.exists(unique_id_file):
            with open(unique_id_file, 'r') as f:
                data_json_updated = json.load(f)
        else:
            data_json_updated = gen_datasets.create_variable_ids(data_json)
            
            with open(unique_id_file, 'w') as f:
                f.write(json.dumps(data_json_updated, indent=4))

        javascript_file_dir = os.path.join(out_dir, "beautified")
        if not os.path.exists(javascript_file_dir):
            gen_datasets.beautify_javascript_files(out_dir)
        javascript_files = os.listdir(javascript_file_dir)
        scripts_json = {} # script IDs to script contents
        scripts_tokenized = {}
        for javascript_file in javascript_files:
            script_id = javascript_file.replace('.ts','')
            with open(os.path.join(javascript_file_dir, javascript_file), 'r') as f:
                script_contents = f.read()
                scripts_json[script_id] = script_contents
                try:
                    scripts_tokenized[script_id] = esprima.tokenize(script_contents, {"loc": True})
                except Exception:
                    pass

        type_dataset_file = os.path.join(out_dir, "type_info.json")
        type_info = get_type_info(data_json_updated, scripts_tokenized)
        with open(type_dataset_file, 'w') as f:
            json.dump(type_info, f, indent=4)
        type_prompts = gen_type_prompts(type_info, scripts_json,out_dir)
        with open(os.path.join(out_dir, "type_prompts.json"), 'w') as f:
            json.dump(type_prompts,f, indent=4)