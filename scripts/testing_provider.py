from app.services.llm import get_llm_provider
import asyncio

async def testing_llm_provider(question: str):
  provider = get_llm_provider()

  try:
    response = await provider.generate(question)
    return response
  except Exception as e:
    return str(e)

if __name__ == "__main__":
  while True:
    ask = input("Enter your question? ")
    if len(ask) > 0:
      result = asyncio.run(testing_llm_provider(ask))
      print(result.answer)
      print(result.tokens_used)
      print(result.model)
    else:
      quit()