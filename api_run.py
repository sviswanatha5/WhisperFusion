from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import asyncio
from transformers import AutoModelForCausalLM, AutoTokenizer
import logging
import torch
import os
from queue import Queue, Empty
from transformers import TextStreamer
import threading

class StopSignal:
    """A unique class to signal stopping the streamer."""
    pass

class CustomStreamer(TextStreamer):
    def __init__(self, tokenizer, skip_prompt=False, **decode_kwargs):
        super().__init__(tokenizer, skip_prompt, **decode_kwargs)
        self.queue = Queue()
        self.last_token_pos = 0  # Track the last token position
        self.stop_event = threading.Event()  # Event to signal stop
        self.first = False

    def put(self, value):
        if self.stop_event.is_set():
            raise StopIteration("Stop signal received, stopping streamer.")
        
        super().put(value)
        
        # Process new tokens from the last processed position
        new_tokens = self.token_cache[self.last_token_pos:]
        new_text = self.tokenizer.decode(new_tokens, **self.decode_kwargs)
        
        # Update the last token position
        self.last_token_pos = len(self.token_cache)
        
        # Add new text to the queue
        if new_text:
            if not self.first:
                self.first = True
            else:
                self.queue.put(new_text)

    def end(self):
        super().end()
        # Spam the queue with stop signals to ensure it is processed
        for _ in range(10):
            self.queue.put(StopSignal())  # End of stream signal

    def get_from_queue(self):
        try:
            item = self.queue.get_nowait()
            if isinstance(item, StopSignal):
                raise StopIteration("Stop signal received, stopping streamer.")
            return item
        except Empty:
            return None

    def set_stop(self):
        self.stop_event.set()
        self.queue.put(StopSignal())  # Ensure the queue processes the stop signal
# Initialize FastAPI app
app = FastAPI()

# Load model and tokenizer
model = None
tokenizer = None

async def load_model():
    global model, tokenizer
    model_name = "internlm/internlm2_5-7b-chat-1m"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)
    model.to("cuda")
    model.eval()
    logging.info("Model loaded successfully")

@app.on_event("startup")
async def startup_event():
    await load_model()

import json

def format_input(query: str) -> str:
    # Parse the JSON string to extract the content
    messages = json.loads(query)
    
    # Assuming the content is always in the 'content' field of the first message
    content = messages[0]['content']
    
    chat_template = """
    当您完成回复后，您必须在句子末尾添加 <|user|> 以表明您已完成。您只能使用英文字母回复。禁止您使用特殊字符。禁止您使用表情符号。
    
    {content} 
    
    """
    return chat_template.format(content=content)

# Set CUDA_LAUNCH_BLOCKING for debugging
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"

async def generate_text(query: str, streamer: CustomStreamer, stop_event: asyncio.Event):
    input_ids = tokenizer(format_input(query), return_tensors="pt").input_ids.to("cuda")
    attention_mask = torch.ones_like(input_ids).to("cuda")

    generation_kwargs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "max_new_tokens": 2048,
        "temperature": 0.1,
        "top_p": 0.1,
        "top_k": 1,
        "do_sample": True,
        "streamer": streamer
    }
    
    def stock_checking_generate():
        try:
            for _ in model.generate(**generation_kwargs):
                if stop_event.is_set():
                    logging.info("Stop event set, stopping generation.")
                    break
        except StopIteration:
            logging.info("Generation stopped by stop signal.")
            return

    await asyncio.to_thread(stock_checking_generate)

async def send_text_from_queue(websocket: WebSocket, streamer: CustomStreamer):
    # Possible here.
    while True:
        try:
            token = streamer.get_from_queue()
            if token:
                await websocket.send_text(token)
            else:
                await asyncio.sleep(0.2)
        except StopIteration:
            logging.info("Stopping text sending due to stop signal.")
            break

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    stop_event = asyncio.Event()
    try:
        logging.info("Connection open")
        while True:
            data = await websocket.receive_text()
            logging.info(f"Received query: {data}")
            streamer = CustomStreamer(tokenizer)
            
            await asyncio.gather(
                generate_text(data, streamer, stop_event),
                send_text_from_queue(websocket, streamer)
            )
    except WebSocketDisconnect:
        logging.info("Client disconnected")
        stop_event.set()
        streamer.set_stop()  # Signal to stop the streamer
    except Exception as e:
        logging.error(f"Error: {e}")
        stop_event.set()
        streamer.set_stop()  # Signal to stop the streamer
    finally:
        # await websocket.close()  # Ensure the WebSocket is closed
        logging.info("WebSocket connection closed")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="12.1.52.176", port=8001)