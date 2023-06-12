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
    while len(encoding.encode(data)) <= num_tokens and (start_index != 0 or end_index < len(script_contents)):
        #if start_index == 0:
        end_index = min(len(script_contents), end_index+5)
        
        start_index = max(0, start_index - 5)
        data = '\n'.join(script_contents[start_index:end_index])
    return data, start_index

def get_script_contents_between_scope(script_contents, start_line, end_line, num_tokens=2000):
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    data = '\n'.join(script_contents[start_line:end_line+1])
    if len(encoding.encode(data)) > num_tokens:
        return None
    else:
        return data
        
def get_scope_info(data_json, scripts_tokenized):
    execution_info = data_json["variableMappings"]
    result = {}
    for info in execution_info:
        for var_name in info:
            var_info = info[var_name]
            if "heapLocation" in var_info:
                heap_location = var_info["heapLocation"]
                scope = var_info["scopeInfo"]
                if scope["scope"] != "global":
                    scope_start_line = scope["startLocation"]["lineNumber"]
                    scope_end_line = scope["endLocation"]["lineNumber"]
                    real_var_name = '_'.join(var_name.split('_')[:-1])
                    script_id = scope["startLocation"]["scriptId"]
                    if script_id in scripts_tokenized:
                        var_definition_line = get_variable_definition_line(scripts_tokenized[script_id], real_var_name, scope_start_line, scope_end_line)
                        if not var_definition_line:
                            continue
                    else:
                        continue
                else:
                    var_definition_line = "global"
                
                
                encoded_scope = encode_scope_to_str(scope)
                
                if encoded_scope in result:
                    if heap_location in result[encoded_scope]:
                        #if var_name not in result[encoded_scope][heap_location]:
                        result[encoded_scope][heap_location][var_name] = var_definition_line
                    else:
                        result[encoded_scope][heap_location] = {}
                        result[encoded_scope][heap_location][var_name] = var_definition_line
                else:
                    result[encoded_scope] = {}
                    result[encoded_scope][heap_location] = {}
                    result[encoded_scope][heap_location][var_name] = var_definition_line

    return result

def get_type(var_info):
    if "className" in var_info:
        return var_info["className"]
    elif "subtype" in var_info:
        return var_info["subtype"]
    else: 
        return var_info["type"]
    

def get_variable_definition_line(tokenized_script, var_name, start_line, end_line):
    start_lines = []
    for token in tokenized_script:
        token_start_line = token.loc.start.line
        token_end_line = token.loc.end.line
        if token_end_line < start_line or token_start_line > end_line:
            continue
        if token.type == "Identifier" and token.value == var_name:
            start_lines.append(token_start_line)
    if len(start_lines):
        return start_lines[0]
    else:
        return None
    

def get_javascript_files(data_dir):
    result = []
    for filename in os.listdir(data_dir):
        if filename.isdigit() or filename.endswith(".js"):
            result.append(os.path.join(data_dir,filename))
    return result

def beautify_javascript_files(data_dir):

    opts = jsbeautifier.default_options
    opts.space_in_empty_paren = False
    opts.space_in_paren = False
    opts.space_after_anon_function = False
    opts.space_after_named_function = False
    opts.indent_size = 4

    javascript_files = get_javascript_files(data_dir)
    os.makedirs(os.path.join(data_dir, "beautified"), exist_ok=True)
    for javascript_file in javascript_files:
        js_content_beautified = jsbeautifier.beautify_file(javascript_file, opts)
        with open(os.path.join(data_dir, "beautified", os.path.basename(javascript_file)), 'w') as f:
            f.write(js_content_beautified)



if __name__ == "__main__":
    extracted_dir = sys.argv[1]
    data_json_files = glob.glob(os.path.join(extracted_dir, "**/data.json"), recursive=True)
    all_alias_prompts = {}
    all_alias_prompts["aliases"] = []
    all_alias_prompts["no_alias"] = []
    all_type_prompts = []
    all_scope_prompts = {}
    all_scope_prompts["exists_outside"] = []
    all_scope_prompts["only_local"] = []
    for data_json_file in data_json_files:
        #if "instagram.com" not in data_json_file:
        #    continue
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
        """
        alias_dataset_file = os.path.join(out_dir, "aliases.json")
        if not os.path.exists(alias_dataset_file):
            aliased_variables = find_aliasing_variables(data_json_updated)
            with open(alias_dataset_file, 'w') as f:
                f.write(json.dumps(aliased_variables, indent=4))
        else:
            with open(alias_dataset_file, 'r') as f:
                aliased_variables = json.load(f)

        scope_dataset_file = os.path.join(out_dir, "scope_info.json")
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
                try:
                    scripts_tokenized[script_id] = esprima.tokenize(script_contents, {"loc": True})
                except Exception:
                    pass

        if True:#not os.path.exists(scope_dataset_file):
            scope_info = get_scope_info(data_json_updated, scripts_tokenized)
            with open(scope_dataset_file, 'w') as f:
                f.write(json.dumps(scope_info, indent=4))
        else:
            with open(scope_dataset_file, 'r') as f:
                scope_info = json.load(f)

        type_dataset_file = os.path.join(out_dir, "type_info.json")
        if True:#not os.path.exists(type_dataset_file):
            type_info = get_type_info(data_json_updated, scripts_tokenized)
            with open(type_dataset_file, 'w') as f:
                json.dump(type_info, f, indent=4)
        else:
            with open(type_dataset_file, 'r') as f:
                type_info = json.load(f)
        scope_prompts = gen_scope_prompts(scope_info, scripts_json, out_dir)
        all_scope_prompts["exists_outside"] += scope_prompts["exists_outside"]
        all_scope_prompts["only_local"] += scope_prompts["only_local"]
        with open(os.path.join(out_dir, "scope_prompts.json"), 'w') as f:
            json.dump(scope_prompts, f, indent=4)
            
        alias_prompts = gen_alias_prompts(aliased_variables, scripts_json)
        all_alias_prompts["aliases"] += alias_prompts["aliases"]
        all_alias_prompts["no_alias"] += alias_prompts["no_alias"]
        with open(os.path.join(out_dir, "alias_prompts.json"),'w') as f:
            json.dump(alias_prompts,f,indent=4)
        type_prompts = gen_type_prompts(type_info, scripts_json,out_dir)
        all_type_prompts += type_prompts
        with open(os.path.join(out_dir, "type_prompts.json"), 'w') as f:
            json.dump(type_prompts,f, indent=4)
        """
    
    #with open("all_alias_prompts.json", 'w') as f:
    #    json.dump(all_alias_prompts, f, indent=4)
    #with open("all_type_prompts.json", 'w') as f:
    #    json.dump(all_type_prompts, f, indent=4)
    #with open("all_scope_prompts.json", 'w') as f:
    #    json.dump(all_scope_prompts, f, indent=4)
    
        
    
        