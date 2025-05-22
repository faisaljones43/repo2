import os
import asyncio
import json
import sqlite3
from dotenv import load_dotenv

from semantic_kernel import Kernel
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from openai import AsyncOpenAI
from mem0 import MemoryClient

from movie_tinder_plugin_5_19_2025 import MovieTinderPlugin, GENRE_MAP

# Load environment variables
load_dotenv()

# Initialize OpenAI Client
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
chat_completion_service = OpenAIChatCompletion(
    ai_model_id="gpt-4o",
    async_client=client,
)

# Initialize Semantic Kernel and plugin
kernel = Kernel()
plugin = MovieTinderPlugin()
kernel.add_plugin(plugin, plugin_name="MovieTinder")

# Initialize Mem0 client
memory = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))
USER_ID = "user123"
AGENT_ID = "movie_agent"

# Setup Agent
agent = ChatCompletionAgent(
    service=chat_completion_service,
    plugins=[plugin],
    name="MovieAgent",
    instructions="""
When the user asks for movie recommendations, do the following *in order* and only emit human-readable text:
1. Call MovieTinder.list_genres() and wait for an answer
2. Call MovieTinder.ask_mood() and wait
3. Call MovieTinder.ask_decade() and wait
4. Call MovieTinder.ask_popularity() and wait
5. Call MovieTinder.ask_runtime() and wait
Then call MovieTinder.recommend_by_preferences() with the collected values.
Finally, print the returned bullet list.
"""
)

# Setup SQLite database
conn = sqlite3.connect('movie_tinder.db')
cursor = conn.cursor()
cursor.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    genre TEXT, mood TEXT, decade TEXT,
    popularity TEXT, runtime TEXT
)""")
cursor.execute("""CREATE TABLE IF NOT EXISTS movie_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    selected_movie TEXT,
    description TEXT
)""")
conn.commit()

# Compare movies
async def compare_movies(selected_title, selected_description, thread=None):
    top_movies = []
    async for resp in agent.invoke_stream(messages="recommend movies", thread=thread):
        for it in resp.items:
            if hasattr(it, "result") and it.result:
                try:
                    top_movies = json.loads(it.result)
                except json.JSONDecodeError:
                    print("Error parsing movie results.")
                    return

    for movie in top_movies:
        if selected_title.lower() in movie['title'].lower():
            print(f"\nSelected Movie: {selected_title}\nDescription: {selected_description}")
            print(f"\nMatched Movie: {movie['title']}\nDescription: {movie['overview']}")
            return
    print("No movie found that matches the selected movie.")

# Main interaction loop
async def interactive_loop():
    thread: ChatHistoryAgentThread | None = None
    print("\n\U0001F3AC Welcome to MovieTinder!")
    collected_inputs = []
    conversation_log = []

    async for resp in agent.invoke_stream(messages="recommend movies", thread=thread):
        thread = resp.thread
        for it in resp.items:
            if hasattr(it, "text") and it.text:
                print(it.text, end="", flush=True)
                user_input = input("\nYou: ").strip()
                conversation_log.append({"role": "assistant", "content": it.text})
                conversation_log.append({"role": "user", "content": user_input})
                collected_inputs.append(user_input)
                async for next_resp in agent.invoke_stream(messages=user_input, thread=thread):
                    thread = next_resp.thread
                    break

    # Store full interaction to Mem0
    memory.add(messages=conversation_log, user_id=USER_ID, agent_id=AGENT_ID)

    if len(collected_inputs) >= 5:
        genre, mood, decade, popularity, runtime = collected_inputs[:5]
        async for resp in agent.invoke_stream(messages=f"{genre}, {mood}, {decade}, {popularity}, {runtime}", thread=thread):
            for it in resp.items:
                if hasattr(it, "result") and it.result:
                    movies = json.loads(it.result)
                    print("\nYour recommendations:")
                    for m in movies:
                        print(f"\n • {m['title']} ({m['release_year']}) — ⭐ {m['vote_average']}\n{m['overview']}")

                    print("\nChoose between the following:")
                    print("1. Hannibal")
                    print("2. Exorcist")
                    choice = input("\nYou: ").strip()
                    if choice == "1":
                        plugin.store_selected_movie("Hannibal", "A chilling psychological thriller about Hannibal Lecter.")
                        await compare_movies("Hannibal", "A chilling psychological thriller about Hannibal Lecter.", thread)
                    elif choice == "2":
                        plugin.store_selected_movie("Exorcist", "A haunting story about the possession of a young girl.")
                        await compare_movies("Exorcist", "A haunting story about the possession of a young girl.", thread)

if __name__ == "__main__":
    asyncio.run(interactive_loop())
