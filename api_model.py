import requests
import logging
import time
import json
import asyncio
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
    def __init__(self, api_url):
        self.api_url = api_url
        self.last_prompt = ""

    # def query(self, messages: List[Dict[str, Any]], conversation_history: ConversationHistory):
        
    #     formatted_prompt = messages[-1]['message']
    #     history_prompt = conversation_history.get_formatted_history(formatted_prompt)
    #     params = {
    #         "query": history_prompt,
    #         "top_p": 0.8,
    #         "top_k": 10,
    #         "temperature": 0.95,
    #         "max_new_tokens": 2048
    #     }
    #     logging.info(f"Sending request to: {self.api_url}")
    #     logging.info(f"Params: {params}")

    #     with requests.get(self.api_url, params=params, stream=True) as response:
    #         logging.info(f"Response status code: {response.status_code}")
    #         if response.status_code == 200:
    #             response_text = ""
    #             for chunk in response.iter_content(1024):
    #                 response_text += chunk.decode('utf-8')
    #                 logging.info(f"Response chunk: {chunk.decode('utf-8')}")
    #                 yield response_text
    #         else:
    #             return "Error: " + response.text

    # def process_transcription(self, transcription_text, conversation_history: ConversationHistory):
    #     try:
    #         llm_response = asyncio.run(self.query([{"speaker": "user", "message": transcription_text}], conversation_history))
    #         yield llm_response
    #     except Exception as e:
    #         logging.error(f"Error querying custom LLM API: {e}")
    #         return None

    def run(self, transcription_queue, audio_queue, llm_queue, conversation_history):
        message_id = 0
        while True:
            transcription_output = transcription_queue.get()
            if transcription_queue.qsize() != 0:
                continue
            
            prompt = transcription_output['prompt'].strip()
            user = transcription_output['uid']

            #logging.info(f"PROMPT: {prompt}, EOS: {transcription_output["eos"]}")
            
            if user not in conversation_history:
                conversation_history[user] = ConversationHistory()
                
            if self.last_prompt == prompt and transcription_output["eos"]:
                self.eos = False
                start = time.time()
                conversation_history[user].add_to_history("user", prompt)
                
                total_response = ""

                current_response = ""
                llm_queue_feed = ""
                
                llm_response = ""
                
                messages = [{"speaker": "user", "message": prompt}]
                formatted_prompt = messages[-1]['message']
                history_prompt = conversation_history[user].get_formatted_history(formatted_prompt)
                params = {
                    "query": history_prompt,
                    "top_p": 0.9,
                    "top_k": 10,
                    "temperature": 0.3,
                    "max_new_tokens": 1024
                }
                logging.info(f"Sending request to: {self.api_url}")
                logging.info(f"Params: {params}")

                with requests.get(self.api_url, params=params, stream=True) as response:
                    logging.info(f"Response status code: {response.status_code}")
                    if response.status_code == 200:
                        for chunk in response.iter_content(1024):
                            logging.info(f"TRANSCRIPTION QUEUE SIZE: {transcription_queue.qsize()}")
                            transcription_output = transcription_queue.get()
                            test = transcription_output["prompt"]
                            logging.info(f"Transciprtion queue contents: {test}")
                            if transcription_output["prompt"] == "":
                                break
                            llm_response = chunk.decode('utf-8')
                            if not llm_response:
                                self.eos = True
                            self.infer_time = time.time() - start
                            if not llm_response and not total_response:
                                llm_response = "The service is currently not available."
                            llm_queue_feed += llm_response
                            logging.info(f"LLM QUEUE FEED: {llm_queue_feed}")
                            llm_queue.put({
                                    "uid": user,
                                    "llm_output": llm_queue_feed,
                                    "eos": self.eos,
                                    "latency": self.infer_time
                                })
                            
                            
                            if any(char in llm_response for char in ['.', '?', '!']):

                                if "." in llm_response:
                                    split = llm_response.split(".")
                                    punc = "."
                                elif "?" in llm_response:
                                    split = llm_response.split("?")
                                    punc = "?"
                                else:
                                    split = llm_response.split("!")
                                    punc = "!"

                                logging.info(f"current chunk: {llm_response}")

                                current_response += split[0] + punc
                                logging.info(f"CURRENT RESPONSE: {current_response}")
                                audio_queue.put({"message_id": message_id, "llm_output": current_response})
                                total_response += current_response

                                current_response = ""
                            else:
                                current_response += llm_response
                                
                            logging.info(f"RESPONSE: {llm_response}")
                            
                            logging.info(f"API INFERENCE TIME: {self.infer_time}")
                            logging.info(f"Response chunk: {chunk.decode('utf-8')}")
                    else:
                        return "Error: " + response.text
                
                conversation_history[user].add_to_history("assistant", total_response)
                #audio_queue.put({"message_id": message_id, "llm_output": llm_response, "eos": self.eos})
                self.last_prompt = ""  # Reset last prompt after processing
                self.eos = False  # Reset eos after processing
                message_id += 1
                continue
            
            self.last_prompt = prompt
            
            #test git