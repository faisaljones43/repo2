from dotenv import load_dotenv
import os
import re
import json
from datetime import datetime
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser
from tmdb_clients import get_movie_details
from vector_store import MovieVectorStore
from memory import save_prefs, recall_prefs
from tmdbv3api import Genre, Discover, TMDb
from ingest import MOVIES_FILE, TMDB_PAGES

load_dotenv()

QUESTIONS = [
    "Would you like to see movies from a specific genre?",
    "What kind of mood? (e.g. lighthearted, intense, adventurous)",
    "Which decade do you prefer? (e.g. 1980s, 1990s, 2000s)",
    "Do you lean toward popular hits or hidden gems?",
    "Any runtime preference? (e.g. < 90 min, 90–120 min, > 120 min)",
    "What country are you in for streaming services? (e.g. US, GB, DE)"
]
KEYS = ["genre","mood","decade","popularity","runtime","region"]
tmdb = TMDb()
tmdb_api_key = os.getenv("TMDB_API_KEY")
discover = Discover()

class MoviePreferenceAgent:
    def __init__(self, user_id="default"):
        self.user_id = user_id
        self.prefs = recall_prefs(user_id) or {}
        self.idx = len(self.prefs)
        self.store = MovieVectorStore(persist_dir="./chroma_db")
        genre_client = Genre()
        all_genres = genre_client.movie_list()
        self.genre_map = {g.name.lower(): g.id for g in all_genres}
        self.id_to_genre = {g.id: g.name for g in all_genres}
        self.llm = ChatOpenAI(temperature=0)
        self.parser = StrOutputParser()
        self.store.ingest(
            movies_json=MOVIES_FILE,
            pages=TMDB_PAGES,
            overwrite=True
        )
        self.summary_chain = (
            ChatPromptTemplate.from_messages([
                ("system", "You are a helpful assistant."),
                ("human", "Here are preferences:\n{preferences}\nMake a short summary.")
            ]) | self.llm | self.parser
        )

    def _build_query(self):
        """Generate search query from preferences using LLM"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Convert these movie preferences to a semantic search query:"),
            ("human", "{prefs}")
        ])
        chain = prompt | self.llm | self.parser
        return chain.invoke({"prefs": str(self.prefs)})

    def _validate_input(self, key: str, value: str):
        value = value.strip().lower()
        if key == "genre":
            if value not in self.genre_map:
                print(f"❗ '{value}' is not a recognized genre. Please try again.")
                return None
            return value
        elif key == "decade":
            match = re.search(r"(\b\d{2,4}s?\b)", value)
            if not match:
                print("❗ Please specify a decade like '1990s' or '80s'")
                return None
            raw_decade = match.group(1).replace("'", "").rstrip('s')
            if len(raw_decade) == 2:
                century = "19" if raw_decade.startswith("9") else "20"
                decade = f"{century}{raw_decade}0s"
            else:
                decade = f"{raw_decade[:-1]}0s"
            return decade
        elif key == "runtime":
            if not re.match(r"^[<>]?\s*\d+(-\d+)?", value):
                print("❗ Please use formats like '<90', '90-120', or '>120'")
                return None
            return value
        elif key == "region":
            if not re.match(r"^[a-zA-Z]{2}$", value.upper()):
                print("❗ Please enter a valid 2-letter country code (e.g. US, GB, DE)")
                return None
            return value.upper()
        return value
    def next_q(self):
        """Get next question or None if completed"""
        return QUESTIONS[self.idx] if self.idx < len(QUESTIONS) else None

    def handle_answer(self, ans: str):
        """Store validated answers and progress"""
        if self.idx >= len(QUESTIONS):
            return None

        key = KEYS[self.idx]
        validated = self._validate_input(key, ans)
        
        if validated:
            self.prefs[key] = validated
            self.idx += 1
        return self.next_q()

    def summary(self):
        """Generate natural language summary of preferences"""
        text = "\n".join(
            f"{QUESTIONS[i]}\n→ {self.prefs[k]}" 
            for i, k in enumerate(KEYS) if k in self.prefs
        )
        return self.summary_chain.invoke({"preferences": text})

    def recommend(self, genre, mood, decade, popularity, runtime, top_n="5") -> str:
        self.prefs.update({
            "genre": genre,
            "mood": mood,
            "decade": decade,
            "popularity": popularity,
            "runtime": runtime
        })
        save_prefs(self.user_id, self.prefs)
        query = self._build_query()
        try:
            n = max(1, int(top_n))
        except ValueError:
            n = 5
        conditions: list[dict] = []

        genre = self.prefs.get("genre", "")
        gid = self.genre_map.get(genre.strip().lower())
        if gid:
            # Use primary_genre_id for filtering
            conditions.append({"primary_genre_id": {"$eq": gid}})
        if not gid:
            return "I couldn’t find that genre—please try again."
        dec = decade.strip().lower()
        year_start, year_end = None, None
        if dec.endswith("s") and dec[:-1].isdigit():
            ys = int(dec[:-1])
            year_start, year_end = ys, ys + 9
        if year_start and year_end:
            conditions.append({"release_year": {"$gte": year_start}})
            conditions.append({"release_year": {"$lte": year_end}})

        rt = runtime.replace(" ", "")
        rt_gte = rt_lte = None
        if "<" in rt:
            try:
                rt_lte = int(rt.split("<")[-1].replace("min", ""))
            except Exception:
                pass
        elif ">" in rt:
            try:
                rt_gte = int(rt.split(">")[-1].replace("min", ""))
            except Exception:
                pass
        elif "-" in rt:
            try:
                low, high = rt.split("-")
                rt_gte = int(low)
                rt_lte = int(high)
            except Exception:
                pass
        if rt_gte is not None:
            conditions.append({"runtime": {"$gte": rt_gte}})
        if rt_lte is not None:
            conditions.append({"runtime": {"$lte": rt_lte}})

        # Get region from preferences (default to 'US' if not set)
        region = self.prefs.get("region", "US")
        from tmdb_clients import get_movie_providers

        # 4) **One** call to search, with keywords
        filters = {"$and": conditions} if conditions else None
        print("DEBUG: Query:", query)
        print("DEBUG: Filters:", filters)
        hits = self.store.search(
            query=query,
            top_n=n,
            filters=filters
        )
        print("DEBUG: Hits:", hits)
        output = []
        if hits:
            for hit in hits:
                details = get_movie_details(int(hit["metadata"]["id"]))
                if "error" in details:
                    continue
                # genre_ids is a comma-separated string, convert to list of ints
                genre_ids_str = hit["metadata"].get("genre_ids", "")
                genre_ids = [int(g) for g in genre_ids_str.split(",") if g]
                genres = [self.id_to_genre.get(g, "Unknown") for g in genre_ids]
                year = (datetime.fromisoformat(details["release_date"]).year if details.get("release_date") else "N/A")
                providers = get_movie_providers(details["id"], region)
                provider_str = (
                    f"Available on: {', '.join(providers)}" if providers else "No streaming info found."
                )
                output.append(
                    f"🎬 {details['title']} ({year})\n"
                    f"⭐ {details.get('vote_average', '?')}/10 | ⏳ {details.get('runtime','?')} mins\n"
                    f"🏷️ {', '.join(genres)}\n"
                    f"📖 {details.get('overview','No description')}\n"
                    f"{provider_str}\n"
                )
        else:
            sort_by = "popularity.desc"
            if popularity and "hidden" in popularity.lower():
                sort_by = "vote_average.asc"

            # Fallback: Use TMDb discover API
            discover_params = {"sort_by": sort_by, "language": "en-US", "page": 1}
            if gid:
                discover_params["with_genres"] = str(gid)
            if decade:
                if year_start and year_end:
                    discover_params["primary_release_date.gte"] = f"{year_start}-01-01"
                    discover_params["primary_release_date.lte"] = f"{year_end}-12-31"
            if rt_gte is not None:
                discover_params["with_runtime.gte"] = rt_gte
            if rt_lte is not None:
                discover_params["with_runtime.lte"] = rt_lte

            # Call TMDb discover API
            raw = list(discover.discover_movies(discover_params))
            # Filter results to ensure genre match (sometimes TMDb returns loose matches)
            filtered = [m for m in raw if gid in [g.id for g in getattr(m, 'genres', [])] or (hasattr(m, 'genre_ids') and gid in getattr(m, 'genre_ids', []))]
            for m in filtered[:n]:
                # Fetch full details to get runtime
                details = get_movie_details(getattr(m, 'id', None))
                genres = [self.id_to_genre.get(g, "Unknown") for g in getattr(m, 'genre_ids', [])]
                release_date = getattr(m, 'release_date', 'N/A')
                # Extract year if possible
                year = release_date[:4] if release_date and len(release_date) >= 4 else "N/A"
                runtime_val = details.get('runtime', None)
                runtime_str = f"{runtime_val} mins" if runtime_val else "N/A"
                # Fetch streaming providers for this movie and region
                providers = get_movie_providers(details["id"], region)
                provider_str = (
                    f"Available on: {', '.join(providers)}" if providers else "No streaming info found."
                )
                output.append(
                    f"\U0001F3AC {getattr(m, 'title', '?')} ({year})\n"
                    f"\u2B50 {getattr(m, 'vote_average', '?')}/10 | \u23F3 {runtime_str}\n"
                    f"\U0001F3F7\uFE0F {', '.join(genres)}\n"
                    f"\U0001F4D6 {getattr(m, 'overview', 'No description')}\n"
                    f"{provider_str}\n"
                )
        return "\n".join(output) or "No recommendations found."