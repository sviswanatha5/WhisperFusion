import requests
import logging
import time
import json
logging.basicConfig(level=logging.INFO)

class ConversationHistory:
    def __init__(self):
        self.history = []

    def add_to_history(self, speaker, message):
        self.history.append({"speaker": speaker, "message": message})

    def get_history(self):
        return "\n".join([f"{entry['speaker']}:{entry['message']}" for entry in self.history])
    
    def clear_history(self):
        self.history = []

class CustomLLMAPI:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            'Authorization': 'Bearer ' + self.api_key,
            'Content-Type': 'application/json'
        }
        self.conv_id = ''
        self.last_prompt = ""
        self.infer_time = 0

    def query(self, message):
        length_string = " Please limit the response to 50 words."
        post_data = {
            "mode": "test",
            "prompt": message + length_string,
            "top_p": 0.9,
            "top_k": 10,
            "temperature": 0.2,
            "repetition_penalty": 1.0,
            "max_new_tokens": 500
        }
        logging.info(f"Sending request to: {self.api_url}")
        logging.info(f"Post data: {post_data}")

        response = requests.post(self.api_url, headers=self.headers, data=json.dumps(post_data))
        
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response text: {response.text}")
        
        if response.status_code == 200:
            response_json = response.json()
            if 'generated_text' in response_json:
                return response_json['generated_text']
            else:
                return "Error: 'generated_text' key not found in the response."
        else:
            return "Error: " + response.text

    def process_transcription(self, transcription_text):
        try:
            llm_response = self.query(transcription_text)
            return llm_response
        except Exception as e:
            print(f"Error querying custom LLM API: {e}")
            return None

    def run(self, transcription_queue, audio_queue, llm_queue, lock):
        conversation_history = {}
        while True:
            transcription_output = transcription_queue.get()
            if transcription_queue.qsize() != 0:
                continue
            
            if transcription_output["uid"] not in conversation_history:
                conversation_history[transcription_output["uid"]] = ConversationHistory()
            
            prompt = transcription_output['prompt'].strip()
            logging.info(f"PROMPT: {prompt}")
                                
            if self.last_prompt == prompt and transcription_output["eos"]:
                self.eos = transcription_output["eos"]
                start = time.time()
                llm_response = self.process_transcription(transcription_output['prompt'])
                logging.info(f"RESPONSE: {llm_response}")
                self.infer_time = time.time() - start
                test = []
                test.append(llm_response)
                audio_queue.put({"llm_output": test, "eos": self.eos})
                llm_queue.put({
                        "uid": transcription_output["uid"],
                        "llm_output": test,
                        "eos": self.eos,
                        "latency": self.infer_time
                    })
                self.last_prompt = ""
                continue
            
            self.last_prompt = prompt