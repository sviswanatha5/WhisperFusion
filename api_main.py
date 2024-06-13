import multiprocessing
import argparse
import threading
import ssl
import time
import sys
import functools
import ctypes
import requests

from multiprocessing import Process, Manager, Value, Queue

from whisper_live.trt_server import TranscriptionServer
# from llm_service import TensorRTLLMEngine  # No longer needed
from tts_service import WhisperSpeechTTS

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

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--whisper_tensorrt_path',
                        type=str,
                        default="/root/TensorRT-LLM/examples/whisper/whisper_small_en",
                        help='Whisper TensorRT model path')
    parser.add_argument('--phi',
                        action="store_true",
                        help='Phi')
    parser.add_argument('--api_url',
                        type=str,
                        required=True,
                        help='RAGflow API URL')
    parser.add_argument('--api_key',
                        type=str,
                        required=True,
                        help='RAGflow API Key')
    parser.add_argument('--user_id',
                        type=str,
                        required=True,
                        help='User ID for RAGflow API')
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_arguments()
    if not args.whisper_tensorrt_path:
        raise ValueError("Please provide whisper_tensorrt_path to run the pipeline.")
        import sys
        sys.exit(0)

    multiprocessing.set_start_method('spawn')
    
    lock = multiprocessing.Lock()
    
    manager = Manager()
    shared_output = manager.list()
    should_send_server_ready = Value(ctypes.c_bool, False)
    transcription_queue = Queue()
    llm_queue = Queue()
    audio_queue = Queue()

    whisper_server = TranscriptionServer()
    whisper_process = multiprocessing.Process(
        target=whisper_server.run,
        args=(
            "0.0.0.0",
            6006,
            transcription_queue,
            llm_queue,
            args.whisper_tensorrt_path,
            should_send_server_ready
        )
    )
    whisper_process.start()

    custom_llm_api = CustomLLMAPI(api_url=args.api_url, api_key=args.api_key, user_id=args.user_id)

    def process_transcription(transcription_text):
        try:
            llm_response = custom_llm_api.query(transcription_text)
            return llm_response
        except Exception as e:
            print(f"Error querying custom LLM API: {e}")
            return None

    def llm_process_function(transcription_queue, audio_queue):
        while True:
            transcription_text = transcription_queue.get()
            if transcription_text:
                llm_response = process_transcription(transcription_text)
                if llm_response:
                    audio_queue.put(llm_response)

    llm_process = multiprocessing.Process(
        target=llm_process_function,
        args=(transcription_queue, audio_queue)
    )
    llm_process.start()

    tts_runner = WhisperSpeechTTS()
    tts_process = multiprocessing.Process(target=tts_runner.run, args=("0.0.0.0", 8888, audio_queue, should_send_server_ready))
    tts_process.start()

    whisper_process.join()
    llm_process.join()
    tts_process.join()
