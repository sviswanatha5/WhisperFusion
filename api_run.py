from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse
from threading import Thread
from queue import Queue
from pydantic import BaseModel
import asyncio
from transformers import TextStreamer, AutoModelForCausalLM, AutoTokenizer

def load_model():
    model_name = "THUDM/glm-4-9b-chat"
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(model_name, trust_remote_code=True)
    model.to("cuda") 
    return model, tokenizer

class CustomStreamer(TextStreamer):
    def __init__(self, queue, tokenizer, skip_prompt, **decode_kwargs) -> None:
        super().__init__(tokenizer, skip_prompt, **decode_kwargs)
        self._queue = queue
        self.stop_text = None
        self.stop_signal = asyncio.Event()

    def on_finalized_text(self, text: str, stream_end: bool = False):
        self._queue.put(text)
        if stream_end:
            self._queue.put(self.stop_text)

    def on_new_token(self, token_id: int):
        token = self.tokenizer.decode([token_id], clean_up_tokenization_spaces=True)
        self._queue.put(token)

app = FastAPI()

model, tokenizer = load_model()

streamer_queue = Queue()
streamer = CustomStreamer(streamer_queue, tokenizer, True)

def format_input(query: str) -> str:
    chat_template = """[gMASK]<sop>
    <|user|>
    {content}
    """
    formatted_input = chat_template.format(content=query)
    return formatted_input

def start_generation(query, max_new_tokens=2048, temperature=0.95, top_p=0.80, top_k=10):
    formatted_query = format_input(query)
    inputs = tokenizer([formatted_query], return_tensors="pt").to("cuda:0")
    input_ids = inputs["input_ids"]
    attention_mask = inputs["attention_mask"]
    generation_kwargs = dict(
        input_ids=input_ids,
        attention_mask=attention_mask,
        streamer=streamer,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k
    )
    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()

async def response_generator(query, max_new_tokens=2048, temperature=0.95, top_p=0.8, top_k=10):
    start_generation(query, max_new_tokens, temperature, top_p, top_k)
    streamer.stop_signal.clear()
    while not streamer.stop_signal.is_set():
        value = await asyncio.to_thread(streamer_queue.get)
        if value is None:
            break
        yield value
        print(value)
        streamer_queue.task_done()
    streamer.stop_signal.clear()



class PostRequest(BaseModel):
    message: str

@app.post('/query-stream/')
async def stop_stream(message: PostRequest):
    temp = message.message
    streamer.stop_signal.set()
    print(f"Message Received: {temp}")

@app.get('/query-stream/')
async def stream(
    query: str,
    max_new_tokens: int = Query(2048, description="Maximum number of new tokens to generate."),
    temperature: float = Query(0.95, description="Temperature for the generation."),
    top_p: float = Query(0.8, description="Top-p (nucleus sampling) parameter."),
    top_k: int = Query(10, description="Top-k parameter.")
):
    print(f'Query received: {query}')
    print(f'Generation parameters - max_new_tokens: {max_new_tokens}, temperature: {temperature}, top_p: {top_p}, top_k: {top_k}')
    return StreamingResponse(response_generator(query, max_new_tokens, temperature, top_p, top_k), media_type='text/event-stream')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="12.1.52.180", port=8001)