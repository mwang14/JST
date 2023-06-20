import sys
import json
import jsbeautifier
import os
import tqdm
import gc

def index_to_coordinates(s, index):
    """Returns (line_number, col) of `index` in `s`."""
    if not len(s):
        return 1, 1
    sp = s[:index+1].splitlines(keepends=True)
    return len(sp), len(sp[-1])

def coordinates_to_index(s, line_number, col):
    s = s.splitlines(keepends=True)
    result = 0
    for i in range(line_number):
        result += len(s[i])
    result += col
    return result

def get_string_at_index(s, index, window=5):
    return s[index-window:index+window]

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

def get_beautifier_opts():
    opts = jsbeautifier.default_options
    opts.space_in_empty_paren = False
    opts.space_in_paren = False
    opts.space_after_anon_function = False
    opts.space_after_named_function = False
    opts.indent_size = 4
    return opts


def inside_indices(i, indices):
    for start,end in indices:
        if i >= start and i <= end:
            return True
    return False


def contains_all_characters(s1, s2):
    for char in s1:
        if s1.count(char) != s2.count(char):
            return False
    return True

def beautified_lines_to_indices(js_content, js_content_beautified, collected_data_dir):
    beautified_lines = js_content_beautified.split('\n')
    cur_index = 0
    results = {}
    prev_index = 0
    for i, line in enumerate(beautified_lines):
        line = line.replace(' ', '').strip()
        if not line:
            continue
        while (not contains_all_characters(line, js_content[prev_index:cur_index])) and cur_index <= len(js_content):
            cur_index += 1
        if cur_index > len(js_content):
            with open(os.path.join(collected_data_dir, "new_data.json"), 'w') as f:
                f.write('')
            print("exited!")
            sys.exit(1)
            return results
        results[(prev_index, cur_index)] = i
        prev_index = cur_index
    return results

def get_line_for_index(indices_to_lines, index):
    largest = 0
    largest_start_line = 0
    if not len(indices_to_lines):
        return None
    for start, end in indices_to_lines:
        if end >= largest:
            largest = end
            largest_start_line = start
        if index >= start and index <= end:
            return indices_to_lines[(start,end)]
    if index >= end:
        return indices_to_lines[(largest_start_line, largest)]
    return None

def get_beautified_line_number(orig_line_number,
                               orig_column_number,
                               start_line_number,
                               start_column_number,
                               script_id,
                               scriptData,
                               debug=False):
    real_line_number = get_real_line_number(start_line_number, orig_line_number)
    real_column_number = get_real_column_number(real_line_number, start_column_number, orig_column_number)
    indices_to_lines = scriptData[script_id]["indices_to_lines"]
    js_content = scriptData[script_id]["js_content"]
    debug_indices_to_lines = {}
    for key in indices_to_lines:
        debug_indices_to_lines[str(key)] = indices_to_lines[key]
    with open(f"/tmp/{script_id}", 'w') as f:
        f.write(json.dumps(debug_indices_to_lines))
    
    start_index = coordinates_to_index(js_content, real_line_number, real_column_number)
    line = get_line_for_index(indices_to_lines, start_index)
    return line

if __name__ == "__main__":
    collected_data = sys.argv[1]
    for collected_data_dir in os.listdir(collected_data):
        collected_data_dir = os.path.join(collected_data, collected_data_dir)
        print(f"running on {collected_data_dir}")
        if False:#os.path.exists(os.path.join(collected_data_dir, "new_data.json")):
            print(f"already ran on {collected_data_dir}!")
            sys.exit(0)
        opts = get_beautifier_opts()
        data_json_file = os.path.join(collected_data_dir, "data.json")
        script_metadata_file = os.path.join(collected_data_dir, "scriptMetadata.json")
        with open(script_metadata_file, 'r') as f:
            metadata = json.load(f)
        
        with open(data_json_file, 'r') as f:
            data = json.load(f)

        scriptData = {}
        count = 0
        new_data = {}
        new_data["variableMappings"] = []
        new_data["executedLines"] = []
        os.makedirs(os.path.join(collected_data_dir, "beautified"), exist_ok=True)
        with tqdm.tqdm(total=len(data["executedLines"])) as pbar:
            for i,line in enumerate(data["executedLines"]):
                pbar.update(1)
                scriptId = line["scriptId"]
                line_number = line["line"]
                column = line["column"]
                start_column = metadata[scriptId]["startColumn"]
                start_line_number = metadata[scriptId]["startLine"]
                real_line_number = get_real_line_number(start_line_number, line_number)
                real_column_number = get_real_column_number(real_line_number, start_column, column)
                scriptPath = os.path.join(collected_data_dir, scriptId)
                if scriptId not in scriptData:
                    scriptData[scriptId] = {}
                    with open(scriptPath, 'r') as f:
                        js_content = f.read()
                    js_content_beautified = jsbeautifier.beautify_file(scriptPath, opts)
                    
                    with open(os.path.join(collected_data_dir, "beautified", f"{scriptId}.ts"), 'w') as f:
                        f.write(js_content_beautified)
                    scriptData[scriptId]["js_content"] = js_content
                    scriptData[scriptId]["js_content_beautified"] = js_content_beautified
                    indices_to_lines = beautified_lines_to_indices(js_content, js_content_beautified, collected_data_dir)
                    scriptData[scriptId]["indices_to_lines"] = indices_to_lines
                else:
                    js_content = scriptData[scriptId]["js_content"]
                    js_content_beautified = scriptData[scriptId]["js_content_beautified"]
                    indices_to_lines = scriptData[scriptId]["indices_to_lines"]

                index = coordinates_to_index(js_content, real_line_number, real_column_number)
                line = get_line_for_index(indices_to_lines, index)
                if line is None:
                    # something went wrong, skip
                    #print("here", scriptId, real_line_number, real_column_number)
                    continue
                result = {}
                result["scriptId"] = scriptId
                result["line"] = line
                new_data["executedLines"].append(result)
                js_content_index = 0
                js_content_beautified_index = 0
        gc.collect()
        with tqdm.tqdm(total=len(data["variableMappings"])) as pbar:
            for i,mapping in enumerate(data["variableMappings"]):
                pbar.update(1)
                variable_bindings_for_line = mapping["variableBindings"]
                call_frame_info_for_line = mapping["callFrameInfo"]
                
                new_variable_bindings_for_line = {}
                for var_name, var_info_all_scopes in variable_bindings_for_line.items():
                    new_variable_bindings_for_line[var_name] = []
                    for var_info_for_scope in var_info_all_scopes:
                        scope_info = var_info_for_scope["scopeInfo"]
                        #print(scope_info)
                        if "startLocation" in scope_info:
                            start_location = scope_info["startLocation"]
                            start_scriptId = start_location["scriptId"]
                            start_location_line = start_location["lineNumber"]
                            start_location_column = start_location["columnNumber"]
                            
                            start_column = metadata[start_scriptId]["startColumn"]
                            start_line_number = metadata[start_scriptId]["startLine"]
                            line = get_beautified_line_number(start_location_line, start_location_column, start_line_number, start_column, start_scriptId, scriptData)
                            #if start_location_line == 1 and start_location_column == 292115:
                            #    print("LINE", line)
                            scope_info["startLocation"].pop("columnNumber")
                            scope_info["startLocation"]["lineNumber"] = line
                        if "endLocation" in scope_info:
                            end_location = scope_info["endLocation"]
                            end_scriptId = end_location["scriptId"]
                            end_location_line = end_location["lineNumber"]
                            end_location_column = end_location["columnNumber"]
                            
                            start_column = metadata[end_scriptId]["startColumn"]
                            start_line_number = metadata[end_scriptId]["startLine"]
                            
                            
                            line = get_beautified_line_number(end_location_line, end_location_column, start_line_number, start_column, end_scriptId, scriptData)
                            scope_info["endLocation"].pop("columnNumber")
                            scope_info["endLocation"]["lineNumber"] = line
                        var_info_for_scope["scopeInfo"] = scope_info
                        new_variable_bindings_for_line[var_name].append(var_info_for_scope)
                        #print(scope_info)
                        #print("###")
                    line_execution_info = {}
                    line_execution_info["callFrameInfo"] = call_frame_info_for_line
                    line_execution_info["variableBindings"] = new_variable_bindings_for_line
                new_data["variableMappings"].append(line_execution_info)
            

    
            if True:#len(new_data["executedLines"]):
                with open(os.path.join(collected_data_dir, "new_data.json"), 'w') as f:
                    json.dump(new_data, f, indent=4, sort_keys=True)
                #print(get_string_at_index(js_content_beautified, js_content_beautified_index, window=1))
        


    
    
    
