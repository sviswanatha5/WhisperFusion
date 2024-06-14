import requests
import logging
import time
logging.basicConfig(level = logging.INFO)

class CustomLLMAPI:
    def __init__(self, api_url, api_key):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {'Authorization': 'Bearer ' + self.api_key}
        self.conv_id = ''
        self.new_conv_url = self.api_url + 'new_conversation?user_id='
        self.completion_url = self.api_url + 'completion'
        self.last_prompt = ""
        self.infer_time = 0

    def query(self, message):
        if not self.conv_id:
            r = requests.get(self.new_conv_url , headers=self.headers)
            self.conv_id = r.json()['data']['id']
            logging.info(r.json()['data'])
        post_data = {
            'conversation_id': self.conv_id,
            'messages': [{
                'role': 'user',
                'content': message
            }],
            'stream': False
        }
        response = requests.post(self.completion_url, json=post_data, headers=self.headers)
        return response.json()['data']['answer']
    
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
            # transcription_text = transcription_queue.get()
            # logging.info(f"Q: {transcription_queue}")
            # if transcription_text:
            #     logging.info(f"TEXt: {transcription_text}")
            #     llm_response = self.process_transcription(transcription_text)
            #     logging.info(f"RESPONSE: {llm_response}")
            #     if llm_response:
            #         audio_queue.put(llm_response)
                    
            
            transcription_output = transcription_queue.get()
            if transcription_queue.qsize() != 0:
                continue
            
            if transcription_output["uid"] not in conversation_history:
                conversation_history[transcription_output["uid"]] = []
            
            prompt = transcription_output['prompt'].strip()
            logging.info(f"PROMPT: {prompt}")
                                
            # if prompt is same but EOS is True, we need that to send outputs to websockets
            if self.last_prompt == prompt and transcription_output["eos"]:
                # lock.acquire()
                self.eos = transcription_output["eos"]
                start = time.time()
                llm_response = self.process_transcription(transcription_output['prompt'])
                logging.info(f"RESPonSe: {llm_response}")
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
                # lock.release()
                continue
                
                # conversation_history[transcription_output["uid"]].append(
                #     (transcription_output['prompt'].strip(), self.last_output[0].strip())
                # )
            self.last_prompt = prompt
                    