import requests
import logging
import time
import json
import asyncio
import threading
import websocket
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

    def query(self, query, user, message_id, llm_queue, audio_queue, conversation_history, events):
        start = time.time()
        event = events[user]
        total_response = ""
        current_response = ""
        llm_queue_feed = ""
        llm_response = ""

        try:
            ws = websocket.WebSocket()
                                    
            ws.connect(self.api_url)
            ws.send(json.dumps(query))
            
            logging.info(f"SUCCESSFULY SENT: {query}")
            
            while not event.is_set():
                logging.info(f"Event {event} status: {event.is_set()}")
            
                llm_response =  ws.recv()
                if not llm_response:
                    continue
                if llm_response == "<|user|>":
                    self.eos = True
                    llm_response = ""
                    event.set()
                self.infer_time = time.time() - start
                llm_queue_feed += llm_response
                if user not in llm_queue:
                    llm_queue[user] = []
                llm_queue[user] += [{
                    "uid": user,
                    "llm_output": llm_queue_feed,
                    "eos": self.eos,
                    "latency": self.infer_time
                }]
                
                
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

                    current_response += split[0] + punc
                    logging.info(f"CURRENT RESPONSE: {current_response}")
                    audio_queue.put({"message_id": message_id, "llm_output": current_response})
                    logging.info(f"SENT TO AUDIO_QUEUE: {current_response}")
                    total_response += current_response

                    current_response = ""
                else:
                    current_response += llm_response
                    
                logging.info(f"RESPONSE: {llm_response}")
                
            ws.close()
            if self.eos == False:
                self.eos = True
                llm_queue[user] += [{
                    "uid": user,
                    "llm_output": llm_queue_feed,
                    "eos": self.eos,
                    "latency": self.infer_time
                }]
                    
        except Exception as e:
            logging.info(f"Exception: {e}")
            pass
                
        conversation_history[user].add_to_history("assistant", total_response)
        self.last_prompt = ""  # Reset last prompt after processing
        self.eos = False  # Reset eos after processing

    def run(self, transcription_queue, audio_queue, llm_queue, conversation_history, events):
        message_id = 0
        while True:
            transcription_output = transcription_queue.get()
            if transcription_queue.qsize() != 0:
                continue
            
            prompt = transcription_output['prompt'].strip()
            user = transcription_output['uid']

            if transcription_output and user in events:
                events[user].set()
            
            if user not in conversation_history:
                conversation_history[user] = ConversationHistory()
                
            if self.last_prompt == prompt and transcription_output["eos"]:
                self.eos = False
                conversation_history[user].add_to_history("user", prompt)
                
                messages = [{"speaker": "user", "message": prompt}]
                formatted_prompt = messages[-1]['message']
                history_prompt = conversation_history[user].get_formatted_history(formatted_prompt)
                
                query = [{"role": "user", "content": history_prompt}]
                logging.info(f"Sending request to: {self.api_url}")
                
                if user in events:
                    events[user].set()
                events[user] = threading.Event()
                logging.info(f"Added to events: {events}")
                logging.info(f"added events ID: {hex(id(events))}")

                thread = threading.Thread(target=self.query, args=(query, user, message_id, llm_queue, audio_queue, conversation_history, events))
                thread.start()

                message_id += 1
            
            self.last_prompt = prompt
            