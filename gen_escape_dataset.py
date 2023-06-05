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
import gen_datasets
import pandas as pd

def get_real_line_number(start_line_number, line_number):
    if line_number < start_line_number:
        return 0
    else:
        return line_number - start_line_number
    
def get_real_column_number(line_number, start_column_number, column_number):
    if line_number == 0:
        return column_number - start_column_number
    else:
        return column_number

def token_to_dict(token, annotation):
    result = {}
    result["value"] = token.value
    result["annotation"] = annotation
    result["type"] = token.type
    return result

def tokenized_script_between_lines(tokenized_script, var_name, start_line, start_column, end_line, end_column):
    result = []
    for token in tokenized_script:
        # 1 indexed
        token_start_line = token.loc.start.line - 1
        token_start_column = token.loc.start.column

        token_end_line = token.loc.end.line - 1
        token_end_column = token.loc.end.column
        if token_end_line < start_line or token_start_line > end_line:
            continue
        elif token_start_line == start_line and token_start_column < start_column:
            continue
        elif token_end_line == end_line and token_start_column > end_column:
            continue
        else:
            if token.type == "Identifier" and token.value == var_name:
                token_dict = token_to_dict(token, 1)
            else:
                token_dict = token_to_dict(token, 0)
            result.append(token_dict)
    #print(result)
    return result

def var_exists_between_lines(tokenized_script, var_name, start_line, start_column, end_line, end_column):
    for token in tokenized_script:
        token_start_line = token.loc.start.line - 1
        token_start_column = token.loc.start.column

        token_end_line = token.loc.end.line - 1
        token_end_column = token.loc.end.column

        if token_end_line < start_line or token_start_line > end_line:
            continue
        elif token_start_line == start_line and token_start_column < start_column:
            continue
        elif token_end_line == end_line and token_start_column > end_column:
            continue
        if token.type == "Identifier" and token.value == var_name:
            return True
        
    return False

def get_javascript_files(data_dir):
    result = []
    for filename in os.listdir(data_dir):
        if filename.isdigit():
            result.append(os.path.join(data_dir,filename))
    return result

def escape_get_scope_info(data_json, scripts_tokenized, metadata):
    execution_info = data_json["variableMappings"]
    result = {}
    
    for info in execution_info:
        for var_name in info:
            var_info = info[var_name]
            real_var_name = '_'.join(var_name.split('_')[:-1])
            if "heapLocation" in var_info:
                heap_location = var_info["heapLocation"]
                scope = var_info["scopeInfo"]
                var_exists = True
                if scope["scope"] != "global":
                    scope_start_line = scope["startLocation"]["lineNumber"]
                    scope_start_column = scope["startLocation"]["columnNumber"]

                    scope_end_line = scope["endLocation"]["lineNumber"]
                    scope_end_column = scope["endLocation"]["columnNumber"]

                    script_id = scope["startLocation"]["scriptId"]
                    metadata_start_column = metadata[script_id]["startColumn"]
                    metadata_start_line_number = metadata[script_id]["startLine"]

                    # Adjust for the real line numbers
                    scope_start_line = get_real_line_number(metadata_start_line_number, scope_start_line)
                    scope_start_column = get_real_column_number(scope_start_line, metadata_start_column, scope_start_column)
                    scope_end_line = get_real_line_number(metadata_start_line_number, scope_end_line)
                    scope_end_column = get_real_column_number(scope_end_line, metadata_start_column, scope_end_column)
                    #print(scripts_tokenized.keys())
                    scope["startLocation"]["lineNumber"] = scope_start_line
                    scope["startLocation"]["columnNumber"] = scope_start_column
                    scope["endLocation"]["lineNumber"] = scope_end_line
                    scope["endLocation"]["columnNumber"] = scope_end_column
                    if script_id in scripts_tokenized:
                        #print(script_id, real_var_name, scope_start_line, scope_start_column, scope_end_line, scope_end_column)
                        var_exists = var_exists_between_lines(scripts_tokenized[script_id], 
                                                                       real_var_name, 
                                                                       scope_start_line,
                                                                       scope_start_column,
                                                                       scope_end_line,
                                                                       scope_end_column)
                        if not var_exists:
                            #print(script_id, real_var_name, scope_start_line, scope_start_column, scope_end_line, scope_end_column)
                            #sys.exit(1)
                            continue
                        #print("here")
                    else:
                        continue
                
                
                encoded_scope = gen_datasets.encode_scope_to_str(scope)
                
                if encoded_scope in result:
                    if heap_location in result[encoded_scope]:
                        #if var_name not in result[encoded_scope][heap_location]:
                        if var_name not in result[encoded_scope][heap_location]:
                            result[encoded_scope][heap_location].append(var_name)
                    else:
                        result[encoded_scope][heap_location] = [var_name]
                else:
                    result[encoded_scope] = {}
                    result[encoded_scope][heap_location] = [var_name]

    return result

# Gets heap locations that persist outside of their scope
def gen_scope_dataset(scope_info, scripts_tokenized):
    result = {"tokens": [], "annotations": [], "label": []}
    
    for scope, heap_locations in scope_info.items():
        if "global" in scope:
            continue
        scope_json = json.loads(scope)
        
        for heap_location in heap_locations:
            #if heap_location in result["local"] or heap_location in result["not_local"]:
            #    continue
            if heap_location == "0":
                continue
            heap_location_result = {}
            exists_outside = False
            for other_scope, other_heap_locations in scope_info.items():
                if other_scope == scope:
                    continue
                if heap_location in other_heap_locations:
                    #print(f"{heap_location} in {scope} exists in {other_scope}")
                    exists_outside = True
                    break
            
            heap_location_result["heap_location"] = heap_location
            heap_location_result["variables"] = heap_locations[heap_location] # this is the list of variables
            heap_location_result["scope"] = scope_json
            start_location = scope_json["startLocation"]
            start_line = start_location["lineNumber"]
            start_column = start_location["columnNumber"]
            end_location = scope_json["endLocation"]
            end_line = end_location["lineNumber"]
            end_column = end_location["columnNumber"]
            script_id = start_location["scriptId"]
            metadata_start_column = metadata[script_id]["startColumn"]
            metadata_start_line_number = metadata[script_id]["startLine"]

            # Adjust for the real line numbers
            start_line = get_real_line_number(metadata_start_line_number, start_line)
            start_column = get_real_column_number(start_line, metadata_start_column, start_column)
            end_line = get_real_line_number(metadata_start_line_number, end_line)
            end_column = get_real_column_number(end_line, metadata_start_column, end_column)

            script_contents = scripts_tokenized[script_id]
            
            var_name = random.choice(heap_locations[heap_location])
            real_var_name = '_'.join(var_name.split('_')[:-1])
            code_snippet = tokenized_script_between_lines(script_contents,real_var_name, start_line, start_column, end_line, end_column)
            
            if not code_snippet:
                continue
            tokens = [(token["value"],token["type"]) for token in code_snippet]
            annotations = [token["annotation"] for token in code_snippet]
            if exists_outside:
                result["tokens"].append(tokens)
                result["annotations"].append(annotations)
                result["label"].append(1)
            else:
                result["tokens"].append(tokens)
                result["annotations"].append(annotations)
                result["label"].append(0)
    return pd.DataFrame.from_dict(result)

if __name__ == "__main__":
    extracted_dir = sys.argv[1]
    output_pickle_directory = sys.argv[2]
    data_json_files = glob.glob(os.path.join(extracted_dir, "**/data.json"), recursive=True)
    
    full_df = pd.DataFrame(columns=["tokens","annotations","labels"])
    print(len(data_json_files))
    for data_json_file in data_json_files:
        #if "instagram.com" not in data_json_file:
        #    continue
        
        out_dir = os.path.dirname(data_json_file)
        script_metadata_file = os.path.join(out_dir, "scriptMetadata.json")
        with open(script_metadata_file, 'r') as f:
            metadata = json.load(f)
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

        javascript_files = get_javascript_files(out_dir)
        scripts_json = {} # script IDs to script contents
        scripts_tokenized = {}
        for javascript_file in javascript_files:
            script_id = javascript_file.replace('.ts','')
            with open(javascript_file, 'r') as f:
                script_contents = f.read()
                scripts_json[script_id] = script_contents
                try:
                    scripts_tokenized[os.path.basename(script_id)] = esprima.tokenize(script_contents, {"loc": True})
                except Exception:
                    pass
        scope_dataset_file = os.path.join(out_dir, "scope_info.json")
        if not os.path.exists(scope_dataset_file):
            scope_info = escape_get_scope_info(data_json_updated, scripts_tokenized, metadata)
            with open(scope_dataset_file, 'w') as f:
                f.write(json.dumps(scope_info, indent=4))
        else:
            with open(scope_dataset_file, 'r') as f:
                scope_info = json.load(f)

        
        res = gen_scope_dataset(scope_info, scripts_tokenized)
        print(f"running on {data_json_file}, had {len(res)}")
        escape_dataset_file = os.path.join(out_dir, "escape_dataset.csv")
        #res.to_csv(escape_dataset_file)
        #full_df = pd.concat([full_df,res])
        output_file = os.path.join(output_pickle_directory, os.path.basename(out_dir)) + ".pkl"
        if len(res):
            res.to_pickle(output_file)
        
        