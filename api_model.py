import requests

class CustomLLMAPI:
    def __init__(self, api_url, api_key, user_id):
        self.api_url = api_url
        self.api_key = api_key
        self.user_id = user_id
        self.headers = {'Authorization': 'Bearer ' + self.api_key}
        self.conv_id = ''
        self.new_conv_url = self.api_url + 'new_conversation?user_id='
        self.completion_url = self.api_url + 'completion'

    def query(self, message):
        if not self.conv_id:
            r = requests.get(self.new_conv_url + self.user_id, headers=self.headers)
            self.conv_id = r.json()['data']['id']
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


    def run(self, transcription_queue, audio_queue):
        while True:
            transcription_text = transcription_queue.get()
            if transcription_text:
                llm_response = self.process_transcription(transcription_text)
                if llm_response:
                    audio_queue.put(llm_response)
                    