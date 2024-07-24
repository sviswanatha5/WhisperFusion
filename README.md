# WhisperFusion


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


**Note**
- Since this code is reliant on an API call for the LLM response, whenever there is a change to the API website, the copy script must be rerun, and the run-whisperfusion.sh file must be changed to reflect this

