import asyncio
import websockets
import json

async def user_interaction(user_id, query, output_file):
    uri = "ws://12.1.52.172:8001/ws"
    while True:
        try:
            async with websockets.connect(uri) as websocket:
                
                await websocket.send(query)
                
                with open(output_file, 'w') as file:
                    while True:
                        response = await websocket.recv()
                        print(f"User {user_id} received: {response}")
                        file.write(response + "\n")
                        file.flush()  
        except websockets.ConnectionClosed:
            print(f"User {user_id} connection closed, retrying...")
            await asyncio.sleep(2)  

async def main():
    
    user1 = {
        "user_id": 1,
        "query": json.dumps([{"role": "user", "content": "What is 1 + 1? Be concise."}]),
        "output_file": "user1_output.txt"
    }
    tasks = [
        asyncio.create_task(user_interaction(user1["user_id"], user1["query"], user1["output_file"])),
    ]

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
