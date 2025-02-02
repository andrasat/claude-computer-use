import asyncio
import os

from anthropic import (
  Anthropic,
)
from anthropic.types.beta import (
  BetaMessageParam,
  BetaTextBlockParam,
)

from app import agent_loop


async def custom_input(prompt: str) -> str:
  return await asyncio.to_thread(input, prompt)

async def asyncio_input(prompt: str) -> str:
  return await asyncio.wait_for(custom_input(prompt), timeout=None)

async def main():
  client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_retries=2
  )

  messages: list[BetaMessageParam] = []

  while True:
    user_input = await asyncio_input("> ")

    if user_input.lower() == "quit":
      break
    elif user_input == "":
      continue

    print(f"User: {user_input}\n---")

    messages.append(BetaMessageParam(
      role="user",
      content=[BetaTextBlockParam(type="text", text=user_input)]
    ))

    messages = await agent_loop(client, messages)

  print("Break!")

async def app():
  print("""
    Welcome to Claude Agent App!

    Type "quit" or press Ctrl+D to exit.
  """)

  await main()

if __name__ == "__main__":
  try:
    asyncio.run(app())
  except (KeyboardInterrupt, EOFError):
    pass
  finally:
    print("Goodbye!")
    exit(0)
