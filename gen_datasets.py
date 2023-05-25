import json
import argparse
import glob
import os
import hashlib
import sys
import tiktoken
import base64
import random


def create_scope_id(scope_info):
    scope = scope_info["scope"]
    start_location = ""
    end_location = ""
    if scope == "global":
        return "global"
     
def encode_scope_to_str(scope):
    return json.dumps(scope)#base64.b64encode(json.dumps(scope).encode('utf-8')).decode('utf-8')

def decode_str_to_scope(encoded_scope):
    return base64.b64decode(encoded_scope).decode('utf-8')

def create_variable_ids(data_json):
    result = {}
    execution_info = data_json["variableMappings"]
    new_variable_bindings = []
    for info in execution_info:
        new_variable_bindings_for_line = {}
        for var_name, all_var_info in info['variableBindings'].items():
            for var_info in all_var_info:
                scope_info = var_info["scopeInfo"]
                scope = scope_info["scope"]
                if scope == "global" or scope == "local" or scope == "block":
                    scope_hash = hashlib.md5(json.dumps(scope_info).encode('utf-8'))
                #else:
                #    scope_info.pop("scope")
                #    scope_hash = hashlib.md5(json.dumps(scope_info).encode('utf-8'))
                    var_id = f"{var_name}_{scope_hash.hexdigest()}"
                    if var_id not in new_variable_bindings_for_line:
                        new_variable_bindings_for_line[var_id] = var_info
        new_variable_bindings.append(new_variable_bindings_for_line)
    result['executedLines'] = data_json['executedLines']
    result["variableMappings"] = new_variable_bindings
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
                    if heapLocation in result:
                        result[heapLocation].add(var_name)
                        #print(heapLocation, result[heapLocation])
                    else:
                        result[heapLocation] = set()
                        result[heapLocation].add(var_name)
    new_result = {}
    for heapLocation, variables in result.items():
        if len(variables) > 1:
            new_result[heapLocation] = list(variables)
    return new_result

def get_first_use_of_variable_in_scope(data_json, var_name):
    for i,line in enumerate(data_json["executedLines"]):
        #print("HI", i)
        variable_mappings = data_json["variableMappings"][i]
        if var_name in variable_mappings:
            return line
    return None

def get_script_section(script_contents, start_index, end_index, num_tokens=2000):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    data = '\n'.join(script_contents[start_index:end_index])
    while len(encoding.encode(data)) <= num_tokens or (start_index == 0 and end_index >= len(script_contents)):
        #if start_index == 0:
        end_index = min(len(script_contents) - 1, end_index+5)
        
        start_index = max(0, start_index - 5)
        data = '\n'.join(script_contents[start_index:end_index])
    return data, start_index
        
def get_scope_info(data_json):
    execution_info = data_json["variableMappings"]
    result = {}
    for info in execution_info:
        for var_name in info:
            var_info = info[var_name]
            if "heapLocation" in var_info:
                heap_location = var_info["heapLocation"]
                scope = var_info["scopeInfo"]
                encoded_scope = encode_scope_to_str(scope)
                if encoded_scope in result:
                    if heap_location in result[encoded_scope]:
                        if var_name not in result[encoded_scope][heap_location]:
                            result[encoded_scope][heap_location].append(var_name)
                    else:
                        result[encoded_scope][heap_location] = [var_name]
                else:
                    result[encoded_scope] = {}
                    result[encoded_scope][heap_location] = [var_name]

    return result

def gen_scope_prompt(code_snippet, var_name, start_line, end_line):
    return f"the variable {var_name} between lines {start_line} and {end_line} is a pointer. Does the pointer still exist outside it's scope? Answer yes or no. \n\n ```\n{code_snippet}\n```"

# Gets heap locations that persist outside of their scope
def gen_scope_prompts(scope_info, scripts_json):
    result = {}
    result["not_local"] = []
    result["local"] = []
    
    for scope, heap_locations in scope_info.items():
        if "global" in scope:
            continue
        scope_json = json.loads(scope)

        for heap_location in heap_locations:
            if heap_location in result["local"] or heap_location in result["not_local"]:
                continue
            heap_location_result = {}
            exists_outside = False
            for other_scope, other_heap_locations in scope_info.items():
                if other_scope == scope:
                    continue
                if heap_location in other_heap_locations:
                    exists_outside = True
            
            heap_location_result["heap_location"] = heap_location
            heap_location_result["variables"] = heap_locations[heap_location] # this is the list of variables
            heap_location_result["scope"] = scope_json
            if exists_outside:
                result["not_local"].append(heap_location_result)
            else:
                result["local"].append(heap_location_result)
    count = 0
    prompts = {}
    prompts["exists_outside"] = []
    prompts["only_local"] = []
    for pointer_data in result["not_local"]:
        scope = pointer_data["scope"]
        start_location = scope["startLocation"]
        start_line = start_location["lineNumber"]
        end_location = scope["endLocation"]
        end_line = end_location["lineNumber"]

        script_id = start_location["scriptId"]
        script_contents = scripts_json[script_id].split('\n')
        code_snippet, new_start_line = get_script_section(script_contents, start_line, end_line)
        var_name = '_'.join(random.choice(pointer_data["variables"]).split('_')[:-1])
        # Need to account for new line numbers for the prompting.
        start_line = start_line - new_start_line
        end_line = end_line - new_start_line
        prompt = gen_scope_prompt(code_snippet, var_name, start_line, end_line)
        prompts["exists_outside"].append(prompt)
    for pointer_data in result["local"]:
        scope = pointer_data["scope"]
        start_location = scope["startLocation"]
        start_line = start_location["lineNumber"]
        end_location = scope["endLocation"]
        end_line = end_location["lineNumber"]

        script_id = start_location["scriptId"]
        script_contents = scripts_json[script_id].split('\n')
        code_snippet, new_start_line = get_script_section(script_contents, start_line, end_line)
        var_name = '_'.join(random.choice(pointer_data["variables"]).split('_')[:-1])
        # Need to account for new line numbers for the prompting.
        start_line = start_line - new_start_line
        end_line = end_line - new_start_line
        prompt = gen_scope_prompt(code_snippet, var_name, start_line, end_line)
        prompts["only_local"].append(prompt)
    return prompts



if __name__ == "__main__":
    extracted_dir = sys.argv[1]
    data_json_files = glob.glob(os.path.join(extracted_dir, "**/new_data.json"), recursive=True)
    for data_json_file in data_json_files:
        if "amazon.com" not in data_json_file:
            continue
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
            data_json_updated = create_variable_ids(data_json)
            
            with open(unique_id_file, 'w') as f:
                f.write(json.dumps(data_json_updated, indent=4))
        alias_dataset_file = os.path.join(out_dir, "aliases.json")
        if not os.path.exists(alias_dataset_file):
            aliased_variables = find_aliasing_variables(data_json_updated)
            with open(alias_dataset_file, 'w') as f:
                f.write(json.dumps(aliased_variables, indent=4))
        scope_dataset_file = os.path.join(out_dir, "scope_info.json")
        if not os.path.exists(scope_dataset_file):
            scope_info = get_scope_info(data_json_updated)
            with open(scope_dataset_file, 'w') as f:
                f.write(json.dumps(scope_info, indent=4))
        else:
            with open(scope_dataset_file, 'r') as f:
                scope_info = json.load(f)
        # Create information needed for scope prompts
        javascript_file_dir = os.path.join(out_dir, "beautified")
        javascript_files = os.listdir(javascript_file_dir)
        scripts_json = {} # script IDs to 
        for javascript_file in javascript_files:
            script_id = javascript_file.replace('.ts','')
            with open(os.path.join(javascript_file_dir, javascript_file), 'r') as f:
                scripts_json[script_id] = f.read()
        print(data_json_file)
        prompts = gen_scope_prompts(scope_info, scripts_json)
        with open(os.path.join(out_dir, "prompts.json"), 'w') as f:
            json.dump(prompts, f, indent=4)
        break

        
    
    
        