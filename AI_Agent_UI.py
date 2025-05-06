
# 1) Standard imports + load .env
import os
import asyncio
import json

# Semantic Kernel imports
from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

# OpenAI client
from openai import AsyncOpenAI
# Your TMDb plugin + helpers (adjust the import to your module name)
from movie_tinder_plugin import MovieTinderPlugin, GENRE_MAP

# 1A) Load environment vars
from dotenv import load_dotenv
import os

load_dotenv(override=True)
print("Endpoint:", os.getenv("AZURE_OPENAI_ENDPOINT"))


# 2) Create the AsyncOpenAI client + wrap in a chat‐completion service
client = AsyncOpenAI(
    api_key=os.environ.get("GITHUB_TOKEN"), 
    base_url="https://models.inference.ai.azure.com/",
)

# Create an AI Service that will be used by the `ChatCompletionAgent`
chat_completion_service = OpenAIChatCompletion(
    ai_model_id="gpt-4o-mini",
    async_client=client,
)

# 3) Build the Kernel and register your plugin
kernel = Kernel()
kernel.add_plugin(MovieTinderPlugin(), plugin_name="MovieTinder")

# 4) Create your Agent
agent = ChatCompletionAgent(
    service   = chat_completion_service,
    plugins   = [MovieTinderPlugin()],
    name      = "MovieAgent",
    instructions = 
        """
When the user asks for movie recommendations, do the following *in order* and only emit human‐readable text:

1. Call MovieTinder.list_genre() and wait for an answer then 
2. Call MovieTinder.ask_mood() wait for the answer then 
3. Call MovieTinder.ask_decade() wait for the answer then
4. Call MovieTinder.ask_popularity() wait for the answer then
5. Call MovieTinder.ask_runtime() wait for the answer and then

Once you have collected all five answers, call:

  MovieTinder.recommend_by_preferences(
    genre='<answer to step 1>',
    mood='<answer to step 2>',
    decade='<answer to step 3>',
    popularity='<answer to step 4>',
    runtime='<answer to step 5>',
    top_n='5'
  )

Finally, print the returned bullet list *as-is* (do not show raw JSON or function payloads).
"""
)
# 5) The async UI loop
async def main():
    thread: ChatHistoryAgentThread | None = None

    print("\n🎬 Welcome to MovieTinder!\n")

    # This trigger will call ask_genre(), then ask_mood(), etc.
    async for resp in agent.invoke_stream(messages="recommend movies", thread=thread):
        thread = resp.thread
        # Print each question in sequence
        for it in resp.items:
            if hasattr(it, "text") and it.text:
                print(it.text, end="", flush=True)

    # Loop through user answers until the final .result 
    while True:
        user_input = input("\nYou: ").strip()
        if not user_input:
            print("Goodbye!")
            break

        async for resp in agent.invoke_stream(messages=user_input, thread=thread):
            thread = resp.thread

            for it in resp.items:
                # 1) If it's a question prompt (ask_mood, ask_decade, etc.)
                if hasattr(it, "text") and it.text:
                    print(it.text, end="", flush=True)

                # 2) Once recommend_by_genre fires, you'll get .result JSON
                elif hasattr(it, "result") and it.result:
                    try:
                        movies = json.loads(it.result)
                    except json.JSONDecodeError:
                        print(it.result)
                    else:
                        print("\nYour recommendations:")
                        for m in movies:
                            print(f" • {m['title']} ({m['release_year']}) — ⭐ {m['vote_average']}")
                    # after printing results, exit or loop back to new session?
                    return

    print()

if __name__ == "__main__":
    asyncio.run(main())
    print("lmao ")