import sys
import json


if __name__ == "__main__":
    data_file = sys.argv[1]
    with open(data_file, 'r') as f:
        data = json.load(f)

    lines = data['executedLines']
    variableMappings = data["variableMappings"]

    results = {}
    for i in range(len(lines) - 1):
        line = lines[i]
        variableMapping = variableMappings[i]
        scriptId = line["scriptId"]
        if scriptId not in results:
            results[scriptId] = {}
        for var,info in variableMapping.items():
            if var not in results[scriptId]:
                results[scriptId][var] = set()
            if "className" in info:
                results[scriptId][var].add(info["className"])
            elif "subtype" in info:
                results[scriptId][var].add(info["subtype"])
            else:
                results[scriptId][var].add(info["type"])
    print(results['13'])
    

    