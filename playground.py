from dotenv import load_dotenv
load_dotenv()
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.playground import Playground, serve_playground_app
from agno.storage.sqlite import SqliteStorage
          
from movie_tinder_plugin import MovieTinderPlugin, GENRE_MAP  # ← your skill
storage_path = "tmp/agents.db"
movie_plugin = MovieTinderPlugin()
movie_agent = Agent(
    name="MovieTinder",
    model=OpenAIChat(id="gpt-4o"),
    tools=[MovieTinderPlugin()],
    instructions=[
        # 1) ask genre
        "When a user asks for movie recommendations, first prompt:",
        "  “Which genre do you prefer? Here are your options:”",
        *[f"    • {g}" for g in GENRE_MAP],  # bullet-list of genres
        "Next, call these methods but do not display the process _in order_, passing JSON strings:",
        "  1) fetch_options(genres='<JSON list>')",
        "  2) quiz_preferences(options='<that JSON>')"
         "3) present numbered options",
        "After recommend_by_genre returns JSON",
        "  3) build_candidates(picks='<that JSON>')",
        "  4) recommend(picks='<step3 JSON>', candidates='<step4 JSON>')",
        "Lastly, take the JSON array returned by recommend and turn it into:",
        "  • Title (Year) — one-sentence overview",
        "Do _not_ print raw JSON; only human-readable bullets."
    ],
    storage=SqliteStorage(table_name="movie_tinder", db_file=storage_path),
    add_datetime_to_instructions=True,
    add_history_to_messages=True,
    num_history_responses=5,
    markdown=True,
)

app = Playground(agents=[movie_agent]).get_app()

if __name__ == "__main__":
    serve_playground_app("playground:app", reload=True)
