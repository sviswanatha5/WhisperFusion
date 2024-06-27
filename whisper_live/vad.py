# original: https://github.com/snakers4/silero-vad/blob/master/utils_vad.py

import os
import subprocess
import torch
import numpy as np
import onnxruntime

import logging
logging.basicConfig(level = logging.INFO)


class VoiceActivityDetection():

    def __init__(self, force_onnx_cpu=True):
        print("downloading ONNX model...")
        path = self.download()
        logging.info("PATH: " + str(path))
        print("loading session")

        opts = onnxruntime.SessionOptions()
        opts.log_severity_level = 3

        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1

        print("loading onnx model")
        if force_onnx_cpu and 'CPUExecutionProvider' in onnxruntime.get_available_providers():
            self.session = onnxruntime.InferenceSession(path, providers=['CPUExecutionProvider'], sess_options=opts)
        else:
            self.session = onnxruntime.InferenceSession(path, providers=['CUDAExecutionProvider'], sess_options=opts)

        print("reset states")
        self.reset_states()
        self.sample_rates = [8000, 16000]

    def _validate_input(self, x, sr: int):
        if x.dim() == 1:
            x = x.unsqueeze(0)
        if x.dim() > 2:
            raise ValueError(f"Too many dimensions for input audio chunk {x.dim()}")

        if sr != 16000 and (sr % 16000 == 0):
            step = sr // 16000
            x = x[:,::step]
            sr = 16000

        if sr not in self.sample_rates:
            raise ValueError(f"Supported sampling rates: {self.sample_rates} (or multiply of 16000)")

        if sr / x.shape[1] > 31.25:
            raise ValueError("Input audio chunk is too short")

        return x, sr

    def reset_states(self, batch_size=1):
        self._state = torch.zeros((2, batch_size, 128)).float()
        self._context = torch.zeros(0)
        self._last_sr = 0
        self._last_batch_size = 0

    def __call__(self, x, sr: int):

        x, sr = self._validate_input(x, sr)
        batch_size = x.shape[0]
        context_size = 64 if sr == 16000 else 32

        if not self._last_batch_size:
            self.reset_states(batch_size)
        if (self._last_sr) and (self._last_sr != sr):
            self.reset_states(batch_size)
        if (self._last_batch_size) and (self._last_batch_size != batch_size):
            self.reset_states(batch_size)

        if not len(self._context):
            self._context = torch.zeros(batch_size, context_size)

        x = torch.cat([self._context, x], dim=1)

        if sr in [8000, 16000]:
            ort_inputs = {'input': x.numpy(), 'state': self._state.numpy(), 'sr': np.array(sr)}
            logging.info(ort_inputs)
            ort_outs = self.session.run(None, ort_inputs)
            out, state = ort_outs
            self._state = torch.from_numpy(state)
        else:
            raise ValueError()

        self._context = x[..., -context_size:]
        self._last_sr = sr
        self._last_batch_size = batch_size

        out = torch.from_numpy(out)
        return out

    def audio_forward(self, x, sr: int, num_samples: int = 512):
        outs = []
        x, sr = self._validate_input(x, sr)
        self.reset_states()

        if x.shape[1] % num_samples:
            pad_num = num_samples - (x.shape[1] % num_samples)
            x = torch.nn.functional.pad(x, (0, pad_num), 'constant', value=0.0)

        for i in range(0, x.shape[1], num_samples):
            wavs_batch = x[:, i:i+num_samples]
            out_chunk = self.__call__(wavs_batch, sr)
            outs.append(out_chunk)

        stacked = torch.cat(outs, dim=1)
        return stacked.cpu()

    @staticmethod
    def download(model_url="https://github.com/snakers4/silero-vad/blob/a9d2b591dea11451d23aa4b480eff8e55dbd9d99/files/silero_vad.onnx"):
        target_dir = os.path.expanduser("~/.cache/whisper-live/")

        # Ensure the target directory exists
        os.makedirs(target_dir, exist_ok=True)

        # Define the target file path
        model_filename = os.path.join(target_dir, "silero_vad.onnx")

        # Check if the model file already exists
        if not os.path.exists(model_filename):
            # If it doesn't exist, download the model using wget
            print("Downloading VAD ONNX model...")
            try:
                subprocess.run(["wget", "-O", model_filename, model_url], check=True)
            except subprocess.CalledProcessError:
                print("Failed to download the model using wget.")
        return model_filename
