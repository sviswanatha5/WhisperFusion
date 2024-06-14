#!/bin/bash -e

test -f /etc/shinit_v2 && source /etc/shinit_v2

echo "Running build-models.sh..."
cd /root/scratch-space/
./build-models.sh

cd /root/WhisperFusion
if [ "$1" != "mistral" ]; then
  exec python3 api_main.py --phi \
                  --whisper_tensorrt_path /root/scratch-space/models/whisper_small_en \
                  --api_url "http://12.1.52.172:8002/generate" \
                  --api_key "ragflow-A2YmVmN2EwMjZlNTExZWZiY2E3MDI0Mm" \
                  
                  
else
  exec python3 main.py --mistral \
                  --whisper_tensorrt_path /root/scratch-space/models/whisper_small_en \
                  --mistral_tensorrt_path /root/scratch-space/models/mistral \
                  --mistral_tokenizer_path teknium/OpenHermes-2.5-Mistral-7B
fi
