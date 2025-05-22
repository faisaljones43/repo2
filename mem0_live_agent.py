from dotenv import load_dotenv
from mem0 import MemoryClient
from openai import OpenAI
import os 
from autogen import ConversableAgent
from tmdbv3api import TMDb, Movie, Discover

load_dotenv()
openai_client = OpenAI()
USER_ID = "movie_recommender_1"

agent = ConversableAgent(
    "chatbot",
    system_message="You are a helpful assistant.",
    llm_config={"config_list": [{"model": "gpt-4o-mini", "api_key": os.getenv("OPENAI_API_KEY")}]},
    code_execution_config=False,
    function_map=None,
    human_input_mode="NEVER",
)
memory_client = MemoryClient()

onboarding_questions = [
    "What genre of movie would you like to watch?",
    "What kind of mood are you in? (e.g. lighthearted, intense, adventurous)",
    "Which decade do you prefer? (e.g. 1980s, 1990s, 2000s)",
    "Do you lean toward popular hits or hidden gems?",
    "Any runtime preference? (e.g. < 90 min, 90–120 min, > 120 min)",
    "What country are you in for streaming services? (e.g. US, GB, DE)"
]

def get_context_awareness(question):
    memory_client.add(
        messages=[{"role": "user", "content": question}],
        user_id=USER_ID,
        categories=["conversation_history"]
    )
    all_memories = memory_client.search(question, user_id=USER_ID)
    context = "\n".join([m["memory"] for m in all_memories])
    prompt = f"""Answer the user question based on the context of previous interactions.\nPrevious interactions: {context}\nQuestion: {question}\n"""
    reply = agent.generate_reply(messages=[{"content": prompt, "role": "user"}])
    memory_client.add(
        messages=[{"role": "assistant", "content": reply}],
        user_id=USER_ID,
        categories=["conversation_history"]
    )
    return reply

def get_user_preferences():
    # Retrieve all user preferences for this user
    prefs = memory_client.search("preferences", user_id=USER_ID, categories=["user_preferences"])
    if prefs:
        prefs_summary = "\n".join([m["memory"] for m in prefs])
        print("Your current preferences are:\n", prefs_summary)
        update = input("Would you like to update your preferences? (y/n): ")
        if update.lower() == "y":
            return onboarding_flow()
        else:
            print("Continuing with your saved preferences.")
            return prefs_summary
    else:
        return onboarding_flow()

def onboarding_flow():
    print("Let's get to know your movie preferences!")
    for q in onboarding_questions:
        user_input = input(f"{q}\n> ")
        memory_client.add(
            messages=[{"role": "user", "content": user_input}],
            user_id=USER_ID,
            categories=["user_preferences"]
        )
    print("Preferences saved! Ask me for a recommendation anytime.")
    # Optionally, return a summary of new preferences
    prefs = memory_client.search("preferences", user_id=USER_ID, categories=["user_preferences"])
    return "\n".join([m["memory"] for m in prefs])

def recommend_movie_from_tmdb(preferences_summary):
    """
    Use TMDb API to recommend a movie based on user preferences summary (string).
    """
    tmdb = TMDb()
    tmdb.api_key = os.getenv("TMDB_API_KEY")
    tmdb.language = "en"
    discover = Discover()

    # Simple extraction from preferences (improve with NLP if needed)
    genre = None
    decade = None
    country = None
    runtime = None
    mood = None
    for line in preferences_summary.split("\n"):
        if "genre" in line.lower():
            genre = line.split(":")[-1].strip()
        if "decade" in line.lower():
            decade = line.split(":")[-1].strip()
        if "country" in line.lower():
            country = line.split(":")[-1].strip()
        if "runtime" in line.lower():
            runtime = line.split(":")[-1].strip()
        if "mood" in line.lower():
            mood = line.split(":")[-1].strip()

    # Map genre to TMDb genre id (simple example, expand as needed)
    genre_map = {
        "action": 28, "adventure": 12, "animation": 16, "comedy": 35, "crime": 80,
        "documentary": 99, "drama": 18, "family": 10751, "fantasy": 14, "history": 36,
        "horror": 27, "music": 10402, "mystery": 9648, "romance": 10749, "science fiction": 878,
        "tv movie": 10770, "thriller": 53, "war": 10752, "western": 37
    }
    genre_id = genre_map.get(genre.lower(), None) if genre else None

    # Build discover params
    params = {"sort_by": "popularity.desc"}
    if genre_id:
        params["with_genres"] = genre_id
    if decade:
        try:
            year = int(decade[:4])
            params["primary_release_date.gte"] = f"{year}-01-01"
            params["primary_release_date.lte"] = f"{year+9}-12-31"
        except:
            pass
    if runtime:
        if "<" in runtime:
            params["with_runtime.lte"] = int(runtime.split("<")[-1].split()[0])
        elif ">" in runtime:
            params["with_runtime.gte"] = int(runtime.split(">")[-1].split()[0])
        elif "-" in runtime:
            parts = runtime.replace("min","").split("-")
            params["with_runtime.gte"] = int(parts[0].strip())
            params["with_runtime.lte"] = int(parts[1].strip())
    if country:
        params["with_original_language"] = country.lower()[:2]

    # Query TMDb
    results = discover.discover_movies(params)
    if results:
        movie = results[0]
        return f"I recommend: {movie.title} ({movie.release_date[:4] if movie.release_date else 'N/A'})\nOverview: {movie.overview}\nTMDb Link: https://www.themoviedb.org/movie/{movie.id}"
    else:
        return "Sorry, I couldn't find a movie matching your preferences. Try updating your preferences or being less specific."

if __name__ == "__main__":
    prefs_summary = get_user_preferences()
    while True:
        user_input = input("You: ")
        if "recommend" in user_input.lower():
            print("movie_recommender:", recommend_movie_from_tmdb(prefs_summary))
        else:
            answer = get_context_awareness(user_input)
            print("movie_recommender:", answer)
