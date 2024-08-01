#!/bin/bash -e

test -f /etc/shinit_v2 && source /etc/shinit_v2

echo "Running build-models.sh..."
cd /root/scratch-space/
./build-models.sh

cd /root/WhisperFusion
exec python3 api_main.py --phi \
                --whisper_tensorrt_path /root/scratch-space/models/whisper_medium \
                --api_url ws://12.1.52.180:8001/ws

