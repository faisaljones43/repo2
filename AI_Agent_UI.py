
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
    api_key=os.environ.get("OPENAI_API_KEY"), 
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
    instructions = """
1) Call MovieTinder.list_genres() to show the user which genres are available.
2) Wait for the user to pick a genre.
3) Call MovieTinder.recommend_by_genre(genre='<their choice>', top_n='5')
4) Return only the plain‐text list that recommend_by_genre produces.
""".strip()
)

# 5) The async UI loop
async def main():
    thread: ChatHistoryAgentThread | None = None
    print("🎬 Welcome to MovieTinder!\n")

    while True:
        user = input("You: ").strip()
        if not user:
            break

        # 1) Send user input, stream back the LLM + function calls
        async for resp in agent.invoke_stream(messages=user, thread=thread):
            thread = resp.thread

            for it in resp.items:
                # 2) If this is our function result (JSON), pretty-print it
                if hasattr(it, "result") and it.result:
                    try:
                        movies = json.loads(it.result)
                    except json.JSONDecodeError:
                        # Not valid JSON? Just print raw
                        print(it.result)
                    else:
                        print("\nYour recommendations:")
                        for m in movies:
                            print(f" • {m['title']} ({m['release_year']}) — ⭐ {m['vote_average']}")
                # 3) Otherwise, any regular LLM text
                elif hasattr(it, "text") and it.text:
                    print(it.text, end="", flush=True)

        # blank line before next prompt
        print()

if __name__ == "__main__":
    asyncio.run(main())