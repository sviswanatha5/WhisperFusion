import requests
import logging
import functools
import time
import json
import asyncio
import threading
import websocket
from queue import Queue
from websockets.sync.server import serve
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

    def start(self, host, port, transcription_queue, audio_queue, llm_queue, conversation_history):
        self.transcription_queue = transcription_queue
        self.audio_queue = audio_queue
        self.llm_queue = llm_queue
        self.conversation_history = conversation_history
        self.events = {}
        logging.info(f"STARTING LLM WEBSOCKET")
        with serve(
            self.run, 
            host, port
            ) as server:
            server.serve_forever()

    def query(self, query, user, message_id):
        start = time.time()
        event = self.events[user]
        total_response = ""
        current_response = ""
        llm_queue_feed = ""
        llm_response = ""

        try:
            ws = websocket.WebSocket()
            logging.info(f"WEBSOCKET: {websocket}")
                                    
            ws.connect(self.api_url)
            logging.info(f"WEBSOCKET CONNECTED")
            ws.send(json.dumps(query))
            
            logging.info(f"SUCCESSFULY SENT: {query}")
            
            while not event.is_set():
                logging.info(f"Event {event} status: {event.is_set()}")
            
                llm_response =  ws.recv()
                if not llm_response:
                    continue
                if "<|user|>" in llm_response:
                    self.eos = True
                    llm_response = ""
                    event.set()
                self.infer_time = time.time() - start
                llm_queue_feed += llm_response
                if user not in self.llm_queue:
                    self.llm_queue[user] = []
                self.llm_queue[user] += [{
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
                    self.audio_queue.put({"message_id": message_id, "llm_output": current_response})
                    logging.info(f"SENT TO AUDIO_QUEUE: {current_response}")
                    total_response += current_response

                    current_response = ""
                else:
                    current_response += llm_response
                    
                logging.info(f"RESPONSE: {llm_response}")
                
            ws.close()
            if self.eos == False:
                self.eos = True
                self.llm_queue[user] += [{
                    "uid": user,
                    "llm_output": llm_queue_feed,
                    "eos": self.eos,
                    "latency": self.infer_time
                }]
                    
        except Exception as e:
            logging.info(f"Exception: {e}")
            pass
                
        self.conversation_history[user].add_to_history("assistant", total_response)
        self.last_prompt = ""  # Reset last prompt after processing
        self.eos = False  # Reset eos after processing

    def run(self, websocket):
        message_id = 0
        while True:

            transcription_output = self.transcription_queue.get()
            if self.transcription_queue.qsize() != 0:
                continue
            
            prompt = transcription_output['prompt'].strip()
            user = transcription_output['uid']

            try:
                websocket.recv()
            except Exception as e:
                if user in self.events:
                    self.events[user].set()

            if transcription_output and user in self.events:
                self.events[user].set()
            
            if user not in self.conversation_history:
                self.conversation_history[user] = ConversationHistory()
                
            if self.last_prompt == prompt and transcription_output["eos"]:
                self.eos = False
                self.conversation_history[user].add_to_history("user", prompt)
                
                messages = [{"speaker": "user", "message": prompt}]
                formatted_prompt = messages[-1]['message']
                history_prompt = self.conversation_history[user].get_formatted_history(formatted_prompt)
                
                query = [{"role": "user", "content": history_prompt}]
                logging.info(f"Sending request to: {self.api_url}")
                
                if user in self.events:
                    self.events[user].set()
                self.events[user] = threading.Event()
                logging.info(f"Added to events: {self.events}")

                thread = threading.Thread(target=self.query, args=(query, user, message_id))
                thread.start()

                message_id += 1
            
            self.last_prompt = prompt
            