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
from api_model import CustomLLMAPI

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
    # parser.add_argument('--api_key',
    #                     type=str,
    #                     required=True,
    #                     help='RAGflow API Key')
    # parser.add_argument('--user_id',
    #                     type=str,
    #                     required=True,
    #                     help='User ID for RAGflow API')
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
    conversation_history = {}

    whisper_server = TranscriptionServer()
    whisper_process = multiprocessing.Process(
        target=whisper_server.run,
        args=(
            "0.0.0.0",
            6006,
            transcription_queue,
            llm_queue,
            args.whisper_tensorrt_path,
            should_send_server_ready,
            conversation_history
        )
    )
    whisper_process.start()

    custom_llm_api = CustomLLMAPI(api_url=args.api_url, api_key=args.api_key)    

    llm_process = multiprocessing.Process(
        target=custom_llm_api.run,
        args=(transcription_queue, audio_queue, llm_queue, conversation_history)
    )
    llm_process.start()

    tts_runner = WhisperSpeechTTS()
    tts_process = multiprocessing.Process(target=tts_runner.run, args=("0.0.0.0", 8888, audio_queue, should_send_server_ready))
    tts_process.start()

    whisper_process.join()
    llm_process.join()
    tts_process.join()
