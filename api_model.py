import requests
import logging
import time
import json
from queue import Queue
from typing import List, Dict, Any
from jinja2 import Template

logging.basicConfig(level=logging.INFO)

class ConversationHistory:
    def __init__(self):
        self.history = []

    def add_to_history(self, speaker, message):
        if len(self.history) > 10:
            self.history.pop(0)
        self.history.append({"speaker": speaker, "message": message})

    def get_formatted_history(self, add_generation_prompt=True):
        template = "{% for message in messages %}{% if message['speaker'] == 'user' %}{{'user\n' + message['message'] + '\n'}}{% elif message['speaker'] == 'assistant' %}{{'assistant\n' + message['message'] + '\n' }}{% else %}{{ 'system\n' + message['message'] + '\n' }}{% endif %}{% endfor %}{% if add_generation_prompt %}{{ 'assistant\n' }}{% endif %}"
        t = Template(template)
        return t.render(messages=self.history, add_generation_prompt=add_generation_prompt)
    
    def clear_history(self):
        self.history = []

class CustomLLMAPI:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.last_prompt = ""

    def query(self, messages: List[Dict[str, Any]], conversation_history: ConversationHistory):
        
        formatted_prompt = messages[-1]['message']
        history_prompt = conversation_history.get_formatted_history(formatted_prompt)
        post_data = {
            "content": history_prompt,
            "top_p": 0.8,
            "top_k": 10,
            "temperature": 0.95,
            "repetition_penalty": 1.0,
            "max_new_tokens": 2048
        }
        logging.info(f"Sending request to: {self.api_url}")
        logging.info(f"Post data: {post_data}")

        response = requests.post(self.api_url, json=post_data)
        
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response text: {response.text}")
        
        if response.status_code == 200:
            response_json = response.json()
            if 'response' in response_json:
                return response_json['response']
            else:
                return "Error: 'response' key not found in the response."
        else:
            return "Error: " + response.text

    def process_transcription(self, transcription_text, conversation_history: ConversationHistory):
        try:
            llm_response = self.query([{"speaker": "user", "message": transcription_text}], conversation_history)
            return llm_response
        except Exception as e:
            logging.error(f"Error querying custom LLM API: {e}")
            return None

    def run(self, transcription_queue, audio_queue, llm_queue, conversation_history):
        while True:
            transcription_output = transcription_queue.get()
            if transcription_queue.qsize() != 0:
                continue
            
            prompt = transcription_output['prompt'].strip()
            user = transcription_output['uid']

            logging.info(f"PROMPT: {prompt}, EOS: {transcription_output["eos"]}")

            if user not in conversation_history:
                conversation_history[user] = ConversationHistory()
                
            if self.last_prompt == prompt and transcription_output["eos"]:
                self.eos = transcription_output["eos"]
                start = time.time()
                conversation_history[user].add_to_history("user", prompt)
                llm_response = self.process_transcription(prompt, conversation_history[user])
                if not llm_response:
                    llm_response = "The service is currently not available"
                logging.info(f"RESPONSE: {llm_response}")
                self.infer_time = time.time() - start
                logging.info(f"API INFERENCE TIME: {self.infer_time}")
                conversation_history[user].add_to_history("assistant", llm_response)
                audio_queue.put({"llm_output": llm_response, "eos": self.eos})
                llm_queue.put({
                        "uid": user,
                        "llm_output": llm_response,
                        "eos": self.eos,
                        "latency": self.infer_time
                    })
                self.last_prompt = ""  # Reset last prompt after processing
                self.eos = False  # Reset eos after processing
                continue
            
            self.last_prompt = prompt
            self.eos = transcription_output["eos"]

# import requests
# import logging
# import time
# import json
# from queue import Queue

# logging.basicConfig(level=logging.INFO)

# class ConversationHistory:
#     def __init__(self):
#         self.history = []

#     def add_to_history(self, speaker, message):
#         self.history.append({"speaker": speaker, "message": message})

#     def get_history(self):
#         return "\n".join([f"{entry['speaker']}:{entry['message']}" for entry in self.history])
    
#     def clear_history(self):
#         self.history = []

# class CustomLLMAPI:
#     def __init__(self, api_url, api_key):
#         self.api_url = api_url
#         self.api_key = api_key
#         self.headers = {
#             'Authorization': 'Bearer ' + self.api_key,
#             'Content-Type': 'application/json'
#         }
#         self.conv_id = ''
#         self.last_prompt = ""
#         self.infer_time = 0
#         self.eos = False

#     def query(self, message):
#         post_data = {
#             "mode": "test",
#             "prompt": message,
#             "top_p": 0.9,
#             "top_k": 10,
#             "temperature": 0.2,
#             "repetition_penalty": 1.0,
#             "max_new_tokens": 500
#         }
#         logging.info(f"Sending request to: {self.api_url}")
#         logging.info(f"Post data: {post_data}")

#         response = requests.post(self.api_url, headers=self.headers, data=json.dumps(post_data))
        
#         logging.info(f"Response status code: {response.status_code}")
#         logging.info(f"Response text: {response.text}")
        
#         if response.status_code == 200:
#             response_json = response.json()
#             if 'generated_text' in response_json:
#                 return response_json['generated_text']
#             else:
#                 return "Error: 'generated_text' key not found in the response."
#         else:
#             return "Error: " + response.text

#     def process_transcription(self, transcription_text):
#         try:
#             llm_response = self.query(transcription_text)
#             return llm_response
#         except Exception as e:
#             print(f"Error querying custom LLM API: {e}")
#             return None

#     def run(self, transcription_queue, audio_queue, llm_queue, lock):
#         conversation_history = {}
#         while True:
#             transcription_output = transcription_queue.get()
#             if transcription_queue.qsize() != 0:
#                 continue
            
#             if transcription_output["uid"] not in conversation_history:
#                 conversation_history[transcription_output["uid"]] = ConversationHistory()
            
#             prompt = transcription_output['prompt'].strip()
#             logging.info(f"PROMPT: {prompt}")
                                
#             if self.last_prompt == prompt and transcription_output["eos"]:
#                 self.eos = transcription_output["eos"]
#                 start = time.time()
#                 llm_response = self.process_transcription(transcription_output['prompt'])
#                 logging.info(f"RESPONSE: {llm_response}")
#                 self.infer_time = time.time() - start
#                 test = []
#                 test.append(llm_response)
#                 audio_queue.put({"llm_output": test, "eos": self.eos})
#                 llm_queue.put({
#                         "uid": transcription_output["uid"],
#                         "llm_output": test,
#                         "eos": self.eos,
#                         "latency": self.infer_time
#                     })
#                 self.last_prompt = ""  # Reset last prompt after processing
#                 self.eos = False  # Reset eos after processing
#                 continue
            
#             self.last_prompt = prompt
#             self.eos = transcription_output["eos"]