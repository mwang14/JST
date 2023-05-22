import json
import argparse
import glob
import os
import hashlib
import sys

def create_scope_id(scope_info):
    scope = scope_info["scope"]
    start_location = ""
    end_location = ""
    if scope == "global":
        return "global"
     

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

def get_scope_info(data_json):
    execution_info = data_json["variableMappings"]
    result = {}
    searched = []
    for info in execution_info:
        for var_name in info:
            if var_name in searched:
                continue
            searched.append(var_name)
            var_info = info[var_name]
            if var_info["scopeInfo"]["scope"] == "local":
                result[var_name] = var_info["scopeInfo"]
    return result

if __name__ == "__main__":
    extracted_dir = sys.argv[1]
    data_json_files = glob.glob(os.path.join(extracted_dir, "**/new_data.json"), recursive=True)
    for data_json_file in data_json_files:
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
        
    
        