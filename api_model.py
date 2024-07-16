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

    def get_formatted_history(self, language, add_generation_prompt=True):
        template = """This is the current conversation history between a user and assistant: 
        {% for message in messages %}{% if message['speaker'] == 'user' %}{{'user\n' + message['message'] + '\n'}}{% elif message['speaker'] == 'assistant' %}{{'assistant\n' + message['message'] + '\n' }}{% else %}{{ 'system\n' + message['message'] + '\n' }}{% endif %}{% endfor %}{% if add_generation_prompt %}{% endif %} 
        Note: The conversation history is provided for context. Do not generate responses that involve both the user and the assistant in a loop. Respond only as the assistant.
        assistant
        Answer in """ + language
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
            functools.partial(self.run, ), 
            host, port
            ) as server:
            server.serve_forever()

    def query(self, query, user, message_id, client_socket, language):
        start = time.time()
        event = self.events[user]
        total_response = ""
        current_response = ""
        llm_queue_feed = ""
        llm_response = ""

        try:
            ws = websocket.WebSocket()
                                    
            ws.connect(self.api_url)
            logging.info(f"WEBSOCKET CONNECTED")
            ws.send(json.dumps(query))
            
            logging.info(f"SUCCESSFULY SENT: {query}")
            
            while not event.is_set():
                try:
                    logging.info(f"CLIENT SOCKET: {client_socket.id}, type: {type(client_socket)}")
                    client_socket.ping()
                    client_socket.send("")
                except Exception as e:
                    logging.exception(e)
                    logging.info("Encountered refresh")
                    # flag = False
                    event.set()
                #logging.info(f"Event {event} status: {event.is_set()}")
            
                llm_response =  ws.recv()
                if not llm_response:
                    continue
                self.infer_time = time.time() - start
                llm_queue_feed += llm_response
                if "<|user|>" in llm_queue_feed or "<|im_end|>" in llm_queue_feed:
                    self.eos = True
                    # flag = False
                    event.set()
                    llm_queue_feed.removesuffix("<|im_end|>")
                    llm_queue_feed.removesuffix("<|user|>")
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
                    if not user in self.audio_queue:
                        self.audio_queue[user] = []
                    self.audio_queue[user] += [{"message_id": message_id, "llm_output": current_response, "language": language}]
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
                
        self.conversation_history[user].add_to_history("assistant", llm_queue_feed)
        self.last_prompt = ""  # Reset last prompt after processing
        self.eos = False  # Reset eos after processing

    def run(self, websocket):
        options = None
        message_id = 0
        while True:

            transcription_output = self.transcription_queue.get()
            if self.transcription_queue.qsize() != 0:
                continue
            
            prompt = transcription_output['prompt'].strip()
            user = transcription_output['uid']

            if not options:
                options = websocket.recv()
                options = json.loads(options)
                logging.info(f"open with options: {options}")
            # try:
            #     websocket.send("")
            #     logging.info(f"Received websocket at : {websocket}")
            # except Exception as e:
            #     logging.info("Connection to websocket closed")
            #     if user in self.events:
            #         self.events[user].set()

            if transcription_output and user in self.events:
                self.events[user].set()
            
            websocket.ping()
            logging.info(f"Websocket: {websocket.id}")
            
            if user not in self.conversation_history:
                self.conversation_history[user] = ConversationHistory()
                
            if self.last_prompt == prompt and transcription_output["eos"]:
                self.eos = False
                self.conversation_history[user].add_to_history("user", prompt)
                
                messages = [{"speaker": "user", "message": prompt}]
                formatted_prompt = messages[-1]['message']
                history_prompt = self.conversation_history[user].get_formatted_history(formatted_prompt, transcription_output["language"])
                
                query = [{"role": "user", "content": history_prompt}]
                logging.info(f"Sending request to: {self.api_url}")
                
                if user in self.events:
                    self.events[user].set()
                self.events[user] = threading.Event()
                logging.info(f"Added to events: {self.events}")
                
                websocket.ping()

                logging.info(f"Websocket: {websocket.id}")

                thread = threading.Thread(target=self.query, args=(query, user, message_id, websocket, transcription_output["language"]))
                thread.start()
                # self.query(query, user, message_id, websocket)
                logging.info("Continuing")

                message_id += 1
            
            self.last_prompt = prompt
            