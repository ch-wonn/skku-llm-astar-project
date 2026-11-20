"""OpenAI-compatible CPU/API adapter; original prompt text is unchanged."""
import os
import openai


class IncompleteLLMResponse(ValueError):
    pass


class ChatGPT:
    def __init__(self, method, sysprompt, example):
        self.id = 0
        self.chat_history = [{'role': 'system', 'content': sysprompt}]
        self.prompt = sysprompt
        self.last_call = None
        if example:
            self.prompt += '\nFollow these examples delimited with “”“ as a guide.\n'.replace('“”“', '“”"')
            for value in example.values():
                index = value.find('\n') + 1
                self.prompt += f'“”"\nUser: {value[:index-1]}\nAssistant: {value[index:]}“”"\n'
                self.chat_history.extend([
                    {'role': 'user', 'content': value[:index-1]},
                    {'role': 'assistant', 'content': value[index:]}])

    def _request(self, messages, max_tokens):
        key = os.environ.get('OPENAI_API_KEY') or openai.api_key
        if not key:
            raise RuntimeError('OPENAI_API_KEY must be supplied externally')
        kw = dict(model=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
                  messages=messages, temperature=0, max_tokens=max_tokens,
                  stop=None, request_timeout=60, api_key=key)
        if os.environ.get('OPENAI_API_BASE'):
            kw['api_base'] = os.environ['OPENAI_API_BASE']
        response = openai.ChatCompletion.create(**kw)
        choice = response['choices'][0]
        self.last_call = {'requested_model': kw['model'],
                          'returned_model': response.get('model'),
                          'usage': dict(response.get('usage') or {}),
                          'finish_reason': choice.get('finish_reason'),
                          'response_text': choice['message'].get('content'),
                          'max_tokens': max_tokens, 'temperature': 0, 'stop': None}
        if choice.get('finish_reason') != 'stop':
            raise IncompleteLLMResponse('LLM response did not finish normally')
        return choice['message']['content']

    def ask(self, prompt, stop=None, max_tokens=100):
        # LLM-A* passes 1000, retaining the original default for this experiment.
        limit = int(os.environ.get('LLM_MAX_OUTPUT_TOKENS', str(max_tokens)))
        return self._request([{'role': 'user', 'content': prompt}], limit)

    def chat(self, query, prompt='', stop=None, max_tokens=100):
        messages = [{'role': 'system', 'content': self.prompt},
                    {'role': 'user', 'content': query}]
        if prompt:
            messages.append({'role': 'assistant', 'content': prompt})
        return self._request(messages, max_tokens)

    def chat_with_image(self, chat_history, stop=None, max_tokens=100):
        return self._request(chat_history, max_tokens)
