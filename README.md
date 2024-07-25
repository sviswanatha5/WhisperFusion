# Multilingual STT/TTS model 


## Features

- **Real-Time Speech-to-Text**: Utilizes OpenAI WhisperLive to convert
  spoken language into text in real-time.

- **Large Language Model Integration**: Adds internllm LLM currently, but can be changed easily through an API call
- **Multilingual Text-to-Speech**: Utilizes Whisper TTS model for english TTS, and uses MeloTTS' models for Spanish, French, Mandarin, and Japanese translations
- **TensorRT Optimization**: Both LLM and Whisper are optimized to
  run as TensorRT engines, ensuring high-performance and low-latency
  processing.
- **torch.compile**: WhisperSpeech uses torch.compile to speed up 
  inference which makes PyTorch code run faster by JIT-compiling PyTorch
  code into optimized kernels.


## Hardware Requirements

- A GPU with at least 24GB of RAM
- For optimal latency, the GPU should have a similar FP16 (half) TFLOPS as the RTX 4090. Here are the [hardware specifications](https://www.techpowerup.com/gpu-specs/geforce-rtx-4090.c3889) for the RTX 4090.


## Getting Started

- Build and Run with docker compose for RTX 3090 and RTX
```bash
mkdir docker/scratch-space
cp docker/scripts/build-* docker/scripts/run-whisperfusion.sh docker/scratch-space/

# Set the CUDA_ARCH environment variable based on your GPU
# Use '86-real' for RTX 3090, '89-real' for RTX 4090, '80-real' for A100
CUDA_ARCH=86-real docker compose build
docker compose up
```

- Start Web GUI on `http://localhost:8000`, where localhost is the server IP


**Note On Running Code**
- Since this code is reliant on an API call for the LLM response, whenever there is a change to the API website, the copy script must be rerun, and the run-whisperfusion.sh file must be changed to reflect this

## Code Explanation

Below is a low-level explanation of how the code works and how the backend interacts with the frontend:

1. When running the command "docker-compose up", this warms up all of the TTS/STT models, while also starting up the 3 servers we call upon, which are the TTS, STT, and LLM servers.
2. The Nginx server, which hosts the website, is also started up when "docker-compose up" is called. 
3. With the website running (main.js), when a user clicks on the microphone button to start recording their voice, an AudioContext object is created which converts audio data into a byte-array. This is then sent through a websocket to the STT Transcription server, which is in the whisper_live/trt_server.py file. 
4. The recv_audio() function in the transcription server is called, in which a new transcription model is created with each new user. A new client object is created and we generate a "EOS" token to indicate the end of a transcription sequence. With the end of this sequence, the transcribed text gets pushed into a transcription queue. 
5. The LLM is constantly listening to see if there is anything new in the transcription queue. Once it pops something off of it, it'll intialize a conversation history if not present, and will query the LLM with the current question, any previous history, and a piece of text of what output language the LLM should respond in. 
6. The LLM's response is streamed, meaning that it comes in word-by-word. Once we get enough words (signaled by punctuation in the response), we will send this chunk of words to an audio queue to get translated into audio. Another queue updates every word, and this is used to generate text on the UI. 
7. Depending on what language output the user selects, that specific model is fed data from the audio queue. The model will then output a byte_array, which represents audio data. This array is sent back to the website through a websocket. A message ID is also sent with the audio byte_array to help with interruptions. 
8. With the audio byte_array sent to the JS, the website will process it and send the audio chunks to a buffer, which will then play the audio. 

## Acknowledgements
We would like to acknowledge Collabora for their WhisperFusion model, which our model is heavily based on. We would also like to acknowledge MeloTTS, whose models are used for non-english TTS. 

