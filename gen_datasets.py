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

def get_first_use_of_variable_in_scope(data_json, var_name):
    for i,line in enumerate(data_json["executedLines"]):
        variable_mappings = data_json["variableMappings"][i]
        if var_name in variable_mappings and variable_mappings[var_name]["type"] != "undefined":
            return line
    return None

def section_too_big(script_contents,start_index, end_index, num_tokens=2000):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    data = '\n'.join(script_contents[start_index:end_index])
    return len(encoding.encode(data)) >= num_tokens

def get_script_section(script_contents, start_index, end_index, num_tokens=2000):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    data = '\n'.join(script_contents[start_index:end_index])
    while len(encoding.encode(data)) <= num_tokens and (start_index != 0 or end_index < len(script_contents)-1):
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

def get_type(var_info):
    if "className" in var_info:
        return var_info["className"]
    elif "subtype" in var_info:
        return var_info["subtype"]
    else: 
        return var_info["type"]
    

def get_variable_definition_line(tokenized_script, var_name, start_line, end_line):
    for token in tokenized_script:
        token_start_line = token.loc.start.line
        token_end_line = token.loc.end.line
        if token_end_line < start_line or token_start_line > end_line:
            continue
        if token.type == "Identifier" and token.value == var_name:
            return token_start_line
    return None

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
            var_definition_line = get_variable_definition_line(scripts_tokenized[script_id], real_var_name, start_line, end_line)
            var_result["line"] = var_definition_line
            var_result["type"] = var_type
            var_result["script_id"] = script_id
            result[var_name] = var_result
    return result

def gen_scope_prompt(code_snippet, var_name, start_line, end_line):
    return f"the variable '{var_name}' between lines {start_line} and {end_line} is a pointer. Does the pointer still exist outside it's scope? Answer yes or no. \n\n ```\n{code_snippet}\n```"

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

def find_other_variable_in_same_script(alias_info,heap_location, var_name, script_id):
    all_variables = {}
    for other_heap_location, variables in alias_info.items():
        if other_heap_location == heap_location:
            continue
        for other_var_name in variables:
            if other_var_name != var_name:
                if variables[other_var_name]["startLocation"]["scriptId"] == script_id:
                    all_variables[other_var_name] = variables[other_var_name]
    other_var = random.choice(list(all_variables.keys()))
    other_var_start_line = all_variables[other_var]["startLocation"]["lineNumber"]
    other_var_end_line = all_variables[other_var]["endLocation"]["lineNumber"]
    return other_var, other_var_start_line, other_var_end_line

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
            if section_too_big(script_contents, start_line, end_line):
                continue
            code_snippet, new_start_line = get_script_section(script_contents, start_line, end_line)
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

            start_line = min(first_var_start_line, second_var_start_line)
            end_line = max(first_var_end_line, second_var_end_line)
            if section_too_big(script_contents, start_line, end_line):
                continue
            code_snippet, new_start_line = get_script_section(script_contents, start_line, end_line)
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

def gen_type_prompt(code_snippet, var_name, line):
    return f"What is the type of '{var_name}' defined on line {line}? \n\n ```\n{code_snippet}\n```"

def gen_type_prompts(type_info, scripts_json):
    result = []
    for var_name, var_info in type_info.items():
        var_result = {}
        script_id = var_info["script_id"]
        line = var_info["line"]
        script_contents = scripts_json[script_id].split('\n')
        code_snippet, new_start_line = get_script_section(script_contents, line, line)
        line = line - new_start_line
        real_var_name = '_'.join(var_name.split('_')[:-1])
        prompt = gen_type_prompt(code_snippet, real_var_name, line)
        var_result["prompt"] = prompt
        var_result["type"] = var_info["type"]
        result.append(var_result)
    return result


if __name__ == "__main__":
    extracted_dir = sys.argv[1]
    data_json_files = glob.glob(os.path.join(extracted_dir, "**/new_data.json"), recursive=True)
    for data_json_file in data_json_files:
        if "instagram.com" not in data_json_file:
            continue
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
            data_json_updated = create_variable_ids(data_json)
            
            with open(unique_id_file, 'w') as f:
                f.write(json.dumps(data_json_updated, indent=4))
        alias_dataset_file = os.path.join(out_dir, "aliases.json")
        if True:#not os.path.exists(alias_dataset_file):
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
        scripts_json = {} # script IDs to script contents
        scripts_tokenized = {}
        for javascript_file in javascript_files:
            script_id = javascript_file.replace('.ts','')
            with open(os.path.join(javascript_file_dir, javascript_file), 'r') as f:
                script_contents = f.read()
                scripts_json[script_id] = script_contents
                scripts_tokenized[script_id] = esprima.tokenize(script_contents, {"loc": True})
        type_dataset_file = os.path.join(out_dir, "type_info.json")
        if not os.path.exists(type_dataset_file):
            type_info = get_type_info(data_json_updated, scripts_tokenized)
            with open(type_dataset_file, 'w') as f:
                json.dump(type_info, f, indent=4)
        else:
            with open(type_dataset_file, 'r') as f:
                type_info = json.load(f)
        print(data_json_file)
        #prompts = gen_scope_prompts(scope_info, scripts_json)
        #with open(os.path.join(out_dir, "prompts.json"), 'w') as f:
        #    json.dump(prompts, f, indent=4)
        #prompts = gen_alias_prompts(aliased_variables, scripts_json)
        #with open(os.path.join(out_dir, "alias_prompts.json"),'w') as f:
        #    json.dump(prompts,f,indent=4)
        prompts = gen_type_prompts(type_info, scripts_json)
        with open(os.path.join(out_dir, "type_prompts.json"), 'w') as f:
            json.dump(prompts,f, indent=4)
        break

        
    
    
        