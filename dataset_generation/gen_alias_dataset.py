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
import jsbeautifier
import gen_datasets

def find_other_variable_in_same_script(alias_info,heap_location, var_name, script_id):
    all_variables = {}
    for other_heap_location, variables in alias_info.items():
        if other_heap_location == heap_location:
            continue
        for other_var_name in variables:
            if other_var_name != var_name:
                if variables[other_var_name]["startLocation"]["scriptId"] == script_id:
                    all_variables[other_var_name] = variables[other_var_name]
    if len(all_variables):
        other_var = random.choice(list(all_variables.keys()))
        other_var_start_line = all_variables[other_var]["startLocation"]["lineNumber"]
        other_var_end_line = all_variables[other_var]["endLocation"]["lineNumber"]
        return other_var, other_var_start_line, other_var_end_line
    else: 
        return None, None, None

def gen_alias_prompt(code_snippet, 
                     first_var_name, 
                     second_var_name, 
                     first_var_start_line, 
                     first_var_end_line, 
                     second_var_start_line, 
                     second_var_end_line):
    return f"Can the variable '{first_var_name}' between lines {first_var_start_line} and {first_var_end_line} point to the same location as the variable '{second_var_name}' between lines {second_var_start_line} and {second_var_end_line}? Answer yes or no. \n\n ```\n{code_snippet}\n```"

def gen_alias_prompts(alias_info, scripts_json):
    result = {}
    result["aliases"] = []
    result["no_alias"] = []
    for heap_location, variables in alias_info.items():
        if len(variables) >= 2:
            first_var = random.choice(list(variables.keys()))
            second_var = None
            for other_var in variables:
                if other_var != first_var:
                    if variables[first_var]["startLocation"]["scriptId"] == variables[other_var]["startLocation"]["scriptId"]:
                        second_var = other_var
            if second_var == None:
                continue
            script_id = variables[first_var]["startLocation"]["scriptId"]
            script_contents = scripts_json[script_id].split('\n')
            first_var_start_line = variables[first_var]["startLocation"]["lineNumber"]
            second_var_start_line = variables[second_var]["startLocation"]["lineNumber"]
            start_line = min(first_var_start_line, second_var_start_line)
            first_var_end_line = variables[first_var]["endLocation"]["lineNumber"]
            second_var_end_line = variables[second_var]["endLocation"]["lineNumber"]
            end_line = max(first_var_end_line, second_var_end_line)
            if gen_datasets.section_too_big(script_contents, start_line, end_line):
                continue
            code_snippet, new_start_line = gen_datasets.get_script_section(script_contents, start_line, end_line)
            first_var_start_line = first_var_start_line - new_start_line
            second_var_start_line = second_var_start_line - new_start_line
            first_var_end_line = first_var_end_line - new_start_line
            second_var_end_line = second_var_end_line - new_start_line
            first_var_name = '_'.join(first_var.split('_')[:-1])
            second_var_name = '_'.join(second_var.split('_')[:-1])
            prompt = gen_alias_prompt(code_snippet, 
                                      first_var_name, 
                                      second_var_name, 
                                      first_var_start_line, 
                                      first_var_end_line, 
                                      second_var_start_line, 
                                      second_var_end_line)
            result["aliases"].append(prompt)

        if len(alias_info) > 1:
            first_var = random.choice(list(variables.keys()))
            script_id = variables[first_var]["startLocation"]["scriptId"]
            script_contents = scripts_json[script_id].split('\n')
            first_var_start_line = variables[first_var]["startLocation"]["lineNumber"]
            first_var_end_line = variables[first_var]["endLocation"]["lineNumber"]
            second_var, second_var_start_line, second_var_end_line = find_other_variable_in_same_script(alias_info, heap_location, first_var, script_id)
            if second_var == None:
                continue

            start_line = min(first_var_start_line, second_var_start_line)
            end_line = max(first_var_end_line, second_var_end_line)
            if gen_datasets.section_too_big(script_contents, start_line, end_line):
                continue
            code_snippet, new_start_line = gen_datasets.get_script_section(script_contents, start_line, end_line)
            first_var_start_line = first_var_start_line - new_start_line
            second_var_start_line = second_var_start_line - new_start_line
            first_var_end_line = first_var_end_line - new_start_line
            second_var_end_line = second_var_end_line - new_start_line
            first_var_name = '_'.join(first_var.split('_')[:-1])
            second_var_name = '_'.join(second_var.split('_')[:-1])
            prompt = gen_alias_prompt(code_snippet, 
                                      first_var_name, 
                                      second_var_name, 
                                      first_var_start_line, 
                                      first_var_end_line, 
                                      second_var_start_line, 
                                      second_var_end_line)
            result["no_alias"].append(prompt)
    return result


def find_aliasing_variables(data_json):
    execution_info = data_json["variableMappings"]
    result = {}
    for info in execution_info:
        for var_name in info:
            var_info = info[var_name]
            if var_info["type"] == "object":
                if "heapLocation" in var_info and var_info["scopeInfo"]["scope"] != "global":
                    heapLocation = var_info["heapLocation"]
                    if heapLocation == "0":
                        continue
                    if heapLocation in result:
                        if var_name not in result[heapLocation]:
                            result[heapLocation][var_name] = var_info["scopeInfo"]
                    else:
                        result[heapLocation] = {}
                        result[heapLocation][var_name] = var_info["scopeInfo"]
    new_result = {}
    for heapLocation, variables in result.items():
        if len(variables) > 1:
            new_result[heapLocation] = list(variables)
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
        
        alias_dataset_file = os.path.join(out_dir, "aliases.json")
        if not os.path.exists(alias_dataset_file):
            aliased_variables = find_aliasing_variables(data_json_updated)
            with open(alias_dataset_file, 'w') as f:
                f.write(json.dumps(aliased_variables, indent=4))
        else:
            with open(alias_dataset_file, 'r') as f:
                aliased_variables = json.load(f)

        javascript_file_dir = os.path.join(out_dir, "beautified")
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
        alias_prompts = gen_alias_prompts(aliased_variables, scripts_json)
        with open(os.path.join(out_dir, "alias_prompts.json"),'w') as f:
            json.dump(alias_prompts,f,indent=4)
    