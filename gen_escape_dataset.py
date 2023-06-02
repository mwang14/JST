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

def token_to_dict(token, annotation):
    result = {}
    result["value"] = token.value
    result["annotation"] = annotation
    result["type"] = token.type
    return result

def tokenized_script_between_lines(tokenized_script, var_name, start_line, end_line):
    result = []
    for token in tokenized_script:
        token_start_line = token.loc.start.line
        token_end_line = token.loc.end.line
        if token_end_line < start_line or token_start_line > end_line:
            continue
        else:
            if token.type == "Identifier" and token.value == var_name:
                token_dict = token_to_dict(token, 1)
            else:
                token_dict = token_to_dict(token, 0)
            result.append(token_dict)
    #print(result)
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
            start_location = scope_json["startLocation"]
            start_line = start_location["lineNumber"]
            end_location = scope_json["endLocation"]
            end_line = end_location["lineNumber"]
            if start_line == end_line:
                continue
            script_id = start_location["scriptId"]
            script_contents = scripts_tokenized[script_id]
            
            var_name = random.choice(list(heap_locations[heap_location].keys()))
            real_var_name = '_'.join(var_name.split('_')[:-1])
            code_snippet = tokenized_script_between_lines(script_contents,real_var_name, start_line, end_line)
            
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
    output_file = sys.argv[2]
    data_json_files = glob.glob(os.path.join(extracted_dir, "**/new_data.json"), recursive=True)
    full_df = pd.DataFrame(columns=["tokens","annotations","labels"])
    for data_json_file in data_json_files:
        #if "instagram.com" not in data_json_file:
        #    continue
        
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
        scope_dataset_file = os.path.join(out_dir, "scope_info.json")
        if not os.path.exists(scope_dataset_file):
            scope_info = gen_datasets.get_scope_info(data_json_updated, scripts_tokenized)
            with open(scope_dataset_file, 'w') as f:
                f.write(json.dumps(scope_info, indent=4))
        else:
            with open(scope_dataset_file, 'r') as f:
                scope_info = json.load(f)

        
        res = gen_scope_dataset(scope_info, scripts_tokenized)
        print(f"running on {data_json_file}, had {len(res)}")
        escape_dataset_file = os.path.join(out_dir, "escape_dataset.csv")
        #res.to_csv(escape_dataset_file)
        full_df = pd.concat([full_df,res])
        full_df.to_pickle(sys.argv[2])