import openai
import logging
import os

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

if __name__ == '__main__' :

    #personal_api_key = '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'
    #personal_api_key = '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'
    personal_api_key = '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'
    openai_interface = OpenAIInterface(api_key=personal_api_key)
    print(openai_interface.predict_text("hello"))