import sys
import json

def parse_lambdanet_line(lambdanet_line):
    filename = lambdanet_line.split('\n')[0].split(' ')[0]
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
        key = f"{filename} {end_line}"
        line_info = {}
        
        variable_name = info[1].replace("'", "").replace(':', '')
        types = info[2:]
        types_indices = [1,3,5,7,9]
        types = [types[i] for i in types_indices]
        types = [type.replace(',','').lower() for type in types]
        line_info["variable_name"] = variable_name
        line_info["types"] = types
        if key not in result:
            result[key] = []
            result[key].append(line_info)
        else:
            result[key].append(line_info)
    return result

"""
sometimes a variable is undefined on its line, because statements can span multiple lines. 
Also objects can have subtypes, so we recurse into it.
"""
def get_variable_types(i, var_name, variableMappings):
    types = set()
    still_undefined = True
    while i < len(variableMappings) and var_name in variableMappings[i] and still_undefined:
        all_types_at_line = set()
        for var_info in variableMappings[i][var_name]:
            if var_info["type"] == "object" and "subtype" in var_info:
                types.add(var_info["subtype"].lower())
            if var_info["type"] == "object" and "className" in var_info:
                types.add(var_info["className"].lower())
            if var_info["type"] == "object":
                types.add("object")
            else:
                types.add(var_info["type"].lower())
        if len(types) == 1:
            if list(types)[0] == 'undefined':
                pass
            else:
                still_undefined = False
        else:
            still_undefined = False
        #types += list(all_types_at_line)
        i += 1
    return list(types)

def get_execution_type_info(execution_results):
    executedLines = execution_results["executedLines"]
    variableMappings = execution_results["variableMappings"]
    result = {}
    for i, line in enumerate(executedLines):
        variable_types = {}
        variables = variableMappings[i]
        script = line["scriptId"] + ".ts"
        line_number = line["line"] + 1 # lambdanet line numbers are 1-indexed so need to offset it
        key = f"{script} {line_number}"
        for var_name in variables:
            variable_types_in_scope = get_variable_types(i, var_name, variableMappings)
            variable_types[var_name] = variable_types_in_scope
            #[print(executedLines[i], variableMappings[i][var_name]) for i in lines]
        if key in result:
            for var_name, types in variable_types.items():
                if var_name in result[key]:
                    result[key][var_name] += types
                else:
                    result[key][var_name] = types
        else:
            result[key] = {}
            for var_name, types in variable_types.items():
                result[key][var_name] = types
    return result

def is_function(types):
    types = [type for type in types if type != 'function']
    types = [type for type in types if type != 'undefined']
    return len(types) == 0

if __name__ == "__main__":
    execution_results_file = sys.argv[1]
    lambdanet_results_file = sys.argv[2]
    with open(execution_results_file, 'r') as f:
        execution_results = json.load(f)
    with open(lambdanet_results_file, 'r') as f:
        lambdanet_results = f.read()
    
    execution_types = get_execution_type_info(execution_results)
    lambdanet_parsed = lambdanet_results.split("=== File: ")
    missed = 0
    caught = 0
    
    for lambdanet_line in lambdanet_parsed:
        if lambdanet_line:
            #print(line)
            lambdanet_predictions = parse_lambdanet_line(lambdanet_line)
            for line in lambdanet_predictions:
                if line in execution_types:
                    for lambdanet_prediction in lambdanet_predictions[line]:
                        var_name = lambdanet_prediction["variable_name"]
                        type = lambdanet_prediction["types"][0]
                        if var_name in execution_types[line]:
                            if type not in execution_types[line][var_name]:
                                if not is_function(execution_types[line][var_name]):
                                    print(var_name, type, execution_types[line][var_name], line)
                                    missed += 1
                                #else:
                                #    caught += 1
                            else:
                                caught += 1
    print(missed, caught)
                        
