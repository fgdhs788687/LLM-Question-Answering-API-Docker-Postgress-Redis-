import asyncio, os, time
from openai import AsyncOpenAI
from dotenv import load_dotenv
load_dotenv()

async def main(ask: str):
  # Define the client:
  client = AsyncOpenAI(
    base_url = os.environ['LLM_BASE_URL'],
    api_key = os.environ['GROQ_API_KEY']
  )

  t0 = time.perf_counter() # Start the counter
  response = await client.chat.completions.create(
    model = os.environ['LLM_MODEL'],
    messages = [{'role': 'user', 'content': f'{ask}'}]
  )

  print(f"answer: {response.choices[0].message.content}")
  print(f'token_used: {response.usage.total_tokens}')
  print(f'latency_ms: {int((time.perf_counter() - t0)*1000)} ms')

ask = input("Enter Your Question: ")
asyncio.run(main(ask))