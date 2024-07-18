cd /root/

git clone https://github.com/myshell-ai/MeloTTS.git

cd MeloTTS

pip install -e .
python -m unidic download
pip install --upgrade botocore