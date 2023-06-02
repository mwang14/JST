import openai
import logging
import os
import sys
import json
import random
import tiktoken
import time

class OpenAIInterface:

    def __init__(self, api_key=None):
        if api_key:
            openai.api_key = api_key
        else:
            openai.api_key = os.getenv("OPENAI_API_KEY")

        if not openai.api_key:
            logging.getLogger('sys').warning(f'[WARN] OpenAIInterface (Init): No OpenAI API key given!')


    def predict_text(self, prompt, max_tokens=100, temp=0.5, mode='davinci', prompt_as_chat=False):
        '''
        Queries OpenAI's GPT-3 model given the prompt and returns the prediction.
        See: openai.Completion.create()
            engine="text-davinci-002"
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0

        @param prompt: Prompt describing what you would like out of the
        @param max_tokens: Length of the response
        @return:
        '''

        try:
            if mode == 'chat':
                if prompt_as_chat:
                    message = prompt
                else:
                    message = [{"role": "user", "content": prompt}]

                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=message
                )
                return response['choices'][0]['message']['content']

            else :
                response = openai.Completion.create(
                    engine="text-davinci-003",
                    prompt=prompt,
                    temperature=temp,
                    max_tokens=max_tokens,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0
                )

                return response.choices[0].text
        except Exception as e:
            logging.getLogger('sys').error(f'[ERROR] OpenAIInterface: Unexpected exception- {e}')
            return ''

def get_types(type_prompts, openai_interface):
    print("predicting types!")
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    filtered_type_prompts = []
    for prompt in type_prompts:
        if len(encoding.encode(prompt["prompt"])) < 3000:
            filtered_type_prompts.append(prompt)
    print("finished filtering types!")
    random_type_prompts = random.sample(filtered_type_prompts, 100)
    result = []
    for type_prompt in random_type_prompts:
        pred_result = {}
        prompt = type_prompt["prompt"]
        var_type = type_prompt["type"]
        pred_result["prompt_info"] = type_prompt
        pred_result["type"] = var_type
        prediction = openai_interface.predict_text(prompt)
        pred_result["prediction"] = prediction
        result.append(pred_result)
        time.sleep(1)
    return result

def get_aliases(alias_prompts, openai_interface):
    print("predicting aliases!")
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    filtered_alias_prompts = {}
    filtered_alias_prompts["aliases"] = []
    filtered_alias_prompts["no_alias"] = []
    for prompt in alias_prompts["aliases"]:
        if len(encoding.encode(prompt)) < 3000 and prompt not in filtered_alias_prompts["aliases"]:
            filtered_alias_prompts["aliases"].append(prompt)
    for prompt in alias_prompts["no_alias"]:
        if len(encoding.encode(prompt)) < 3000 and prompt not in filtered_alias_prompts["no_alias"]:
            filtered_alias_prompts["no_alias"].append(prompt)
    aliases = random.sample(filtered_alias_prompts["aliases"], 50)
    no_alias = random.sample(filtered_alias_prompts["no_alias"], 50)

    result = []
    for prompt in aliases:
        prompt_result = {}
        prompt_result["prompt"] = prompt
        prompt_result["aliases"] = "yes"
        prediction = openai_interface.predict_text(prompt)
        prompt_result["prediction"] = prediction
        result.append(prompt_result)
        time.sleep(1)
    for prompt in no_alias:
        prompt_result = {}
        prompt_result["prompt"] = prompt
        prompt_result["aliases"] = "no"
        prediction = openai_interface.predict_text(prompt)
        prompt_result["prediction"] = prediction
        result.append(prompt_result)
        time.sleep(1)
    return result

def get_scopes(scope_prompts, openai_interface):
    print("predicting scopes!")
    encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    filtered_scope_prompts = {}
    filtered_scope_prompts["exists_outside"] = []
    filtered_scope_prompts["only_local"] = []
    seen_prompts = []
    for prompt in scope_prompts["exists_outside"]:
        if len(encoding.encode(prompt["prompt"])) < 3000 and \
        "line 1 " not in prompt["prompt"] and \
              prompt["prompt"] not in seen_prompts and \
                "line 0 " not in prompt["prompt"]:
            filtered_scope_prompts["exists_outside"].append(prompt)
            seen_prompts.append(prompt["prompt"])
    for prompt in scope_prompts["only_local"]:
        if len(encoding.encode(prompt["prompt"])) < 3000 and prompt["prompt"] not in seen_prompts and "line 1 " not in prompt["prompt"]:
            filtered_scope_prompts["only_local"].append(prompt)
            seen_prompts.append(prompt["prompt"])
    print("finished filtering scopes!")
    exists_outside = random.sample(filtered_scope_prompts["exists_outside"],50)
    only_local = random.sample(filtered_scope_prompts["only_local"], 50)
    result = []
    for prompt in exists_outside:
        prompt_result = {}
        prompt_result["prompt_info"] = prompt
        prompt_result["exists_outside"] = "yes"
        prediction = openai_interface.predict_text(prompt["prompt"])
        prompt_result["prediction"] = prediction
        result.append(prompt_result)
        time.sleep(1)
    for prompt in only_local:
        prompt_result = {}
        prompt_result["prompt_info"] = prompt
        prompt_result["exists_outside"] = "no"
        prediction = openai_interface.predict_text(prompt["prompt"])
        prompt_result["prediction"] = prediction
        result.append(prompt_result)
        time.sleep(1)
    return result

if __name__ == '__main__' :
    out_dir = sys.argv[1]
    #personal_api_key = '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'
    #personal_api_key = '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'
    personal_api_key = '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'
    with open("all_type_prompts.json", 'r') as f:
        type_prompts = json.load(f)
    with open("all_alias_prompts.json", 'r') as f:
        alias_prompts = json.load(f)
    with open("all_scope_prompts.json", 'r') as f:
        scope_prompts = json.load(f)
    openai_interface = OpenAIInterface(api_key=personal_api_key)

    #type_preds = get_types(type_prompts, openai_interface)
    #with open(os.path.join(out_dir,"type_results.json"), 'w') as f:
    #    json.dump(type_preds, f, indent=4)
    scope_preds = get_scopes(scope_prompts, openai_interface)
    with open(os.path.join(out_dir, "scope_results.json"), 'w') as f:
        json.dump(scope_preds,f,indent=4)
    #alias_preds = get_aliases(alias_prompts, openai_interface)
    #with open("alias_results.json", 'w') as f:
    #    json.dump(alias_preds,f,indent=4)

    
    