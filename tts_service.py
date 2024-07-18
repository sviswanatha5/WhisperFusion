import functools
import time
import logging
logging.basicConfig(level = logging.INFO)
from tqdm import tqdm
from websockets.sync.server import serve
from whisperspeech.pipeline import Pipeline
import json
import base64
from transformers import pipeline
from melo.api import TTS

device="cuda:1"
speed = 1.0
    


class WhisperSpeechTTS:
    def __init__(self):
        pass

    def initialize_model(self):
        self.pipe = Pipeline(t2s_ref='collabora/whisperspeech:t2s-v1.95-medium-7lang.model', s2a_ref='collabora/whisperspeech:s2a-v1.95-medium-7lang.model', torch_compile=True, device="cuda:1")
        self.models = {
            'es': TTS(language='ES', device=device),
            'fr': TTS(language='FR', device=device),
            'zh': TTS(language='ZH', device=device),
            'jp': TTS(language='JP', device=device),
            'kr': TTS(language='KR', device=device),
        }

        self.last_llm_response = None


    def generate_text(self, language, llm_output):
        if language == 'en':
            stoks = self.pipe.t2s.generate(llm_output, cps=14, lang=language)
            stoks = stoks[stoks!=512]
            atoks = self.pipe.s2a.generate(stoks, self.pipe.default_speaker)
            audio = self.pipe.vocoder.decode(atoks)
            return audio.cpu().numpy()
        else:
            return self.models[language].tts_to_file(llm_output, self.models[language].hps.data.spk2id[language.upper()], None, speed=speed)

    def run(self, host, port, audio_queue=None, should_send_server_ready=None):
        # initialize and warmup model
        self.initialize_model()
        logging.info("\n[WhisperSpeech INFO:] Warming up torch compile model. Please wait ...\n")
        for _ in tqdm(range(3), desc="Warming up"):
            warmup = time.time()
            self.pipe.generate("Hello, I am warming up.")
            for key, value in self.models.items():
                value.tts_to_file("Hello, I am warming up.", value.hps.data.spk2id[key.upper()], None, speed=speed)
            final = time.time() - warmup
            logging.info(f"[WhisperSpeech INFO:] Inference finished in {final}")
        logging.info("[WhisperSpeech INFO:] Warmed up Whisper Speech torch compile model. Connect to the WebGUI now.")
        should_send_server_ready.value = True
        with serve(
            functools.partial(self.start_whisperspeech_tts, audio_queue=audio_queue), 
            host, port
            ) as server:
            server.serve_forever()
    def start_whisperspeech_tts(self, websocket, audio_queue=None):
        self.output_audio = None
        last_message_id = None

        user = None

        while True:
            if not user:
                uid = websocket.recv()
                uid = json.loads(uid)
                user = uid["id"]
                continue
            if not user in audio_queue or len(audio_queue[user]) == 0:
                continue
            logging.info(f"audio_queue {audio_queue}")
            temp = audio_queue[user]
            llm_response = temp.pop(0)
            audio_queue[user] = temp
            logging.info(f"llm_response: {llm_response}")
            # if audio_queue.qsize() != 0:
            #     continue
            
            # check if this websocket exists
            try:
                websocket.ping()
            except Exception as e:
                del websocket
                audio_queue[user] += llm_response
                break
            
            llm_output = llm_response["llm_output"]
            logging.info(f"[WhisperSpeech INFO:] LLM Response: {llm_output} \n\n")
            message_id = llm_response["message_id"]
            if not last_message_id:
                last_message_id = message_id
            
            logging.info(f"MESSAGE_ID: {message_id}")
            if message_id > last_message_id:
                last_message_id = message_id
            def should_abort():
                if not audio_queue.empty(): raise TimeoutError()
            # only process if the output updated
            try:
                if self.last_llm_response != llm_output.strip():
                    logging.info(f"Audio getting processed: {llm_output.strip()} .\n\n")

                    start = time.time()

                    help = llm_response["language"]
                    logging.info(f"Detected language: {help}")
                    self.output_audio = self.generate_text(help, llm_output)
                    inference_time = time.time() - start
                    logging.info(f"[WhisperSpeech INFO:] TTS inference done in {inference_time} ms for  SENTENCE: {llm_output.strip()}.\n\n")
                    self.last_llm_response = llm_output.strip()
            except TimeoutError:
                logging.info("ENTERED TIMEOUTERROR")
                pass
            except RuntimeError as e:
                logging.info(f"ENTERED RUNTIMEERROR: {e}")
                continue
            except Exception as e:
                logging.info(f"ENTERED ERROR: {e}")
            if self.output_audio is not None:
                try:
                    websocket.send(message_id.to_bytes(4, 'big') + self.output_audio.tobytes())
                except Exception as e:
                    logging.error(f"[WhisperSpeech ERROR:] Audio error: {e}")