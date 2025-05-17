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
    "Any runtime preference? (e.g. < 90 min, 90–120 min, > 120 min)"
]
KEYS = ["genre","mood","decade","popularity","runtime"]
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
        discover = Discover()
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
        # Build a Mongo‐style filter dict
        conditions: list[dict] = []

        genre = self.prefs.get("genre", "")
        gid = self.genre_map.get(genre.strip().lower())
        if gid:
            conditions.append({"genre_ids": {"$in": [gid]}})
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
            rt_lte = int(rt.split("<")[-1].replace("min",""))
        elif ">" in rt:
            rt_gte = int(rt.split(">")[-1].replace("min",""))
        elif "-" in rt:
            low, high = rt.split("-")
            rt_gte, rt_lte = int(low.replace("min","")), int(high.replace("min",""))
        if rt_gte is not None:
            conditions.append({"runtime": {"$gte": rt_gte}})
        if rt_lte is not None:
            conditions.append({"runtime": {"$lte": rt_lte}})

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
                # hit["id"] is string—fetch full details
                details = get_movie_details(int(hit["metadata"]["id"]))
                if "error" in details:
                    continue
                # metadata.genre_ids is already a list
                genres = [self.id_to_genre.get(g, "Unknown") for g in hit["metadata"].get("genre_ids",[])]

                year = (datetime.fromisoformat(details["release_date"])
                        .year if details.get("release_date") else "N/A")

                output.append(
                    f"🎬 {details['title']} ({year})\n"
                    f"⭐ {details.get('vote_average', '?')}/10 | ⏳ {details.get('runtime','?')} mins\n"
                    f"🏷️ {', '.join(genres)}\n"
                    f"📖 {details.get('overview','No description')}\n"
                )
        else:
            sort_by = "popularity.desc"
            if "hidden" in popularity.lower():
                sort_by = "vote_average.desc"

            # Fallback: Use TMDb discover API
            discover_params ={            
            }
            if genre:
                gid = self.genre_map.get(genre.strip().lower())
                if gid:
                    discover_params["genre"] = gid
                if not gid: 
                    return "I couldn’t find that genre—please try again."
            if decade:
                if decade.endswith("s") and decade[:-1].isdigit():
                    ys = int(decade[:-1])
                    year_start, year_end = ys, ys + 9
                    discover_params["primary_release_date.gte"] = f"{ys}-01-01"
                    discover_params["primary_release_date.lte"] = f"{ys+9}-12-31"
            if popularity and "hit" in popularity:
                discover_params["sort_by"] = "popularity.desc"
            #Runtime Filters
            rt = runtime.replace(" ", "")
            rt_gte = rt_lte = None
            if "<" in rt:
                rt_lte = int(rt.split("<")[-1].replace("min",""))
            elif ">" in rt:
                rt_gte = int(rt.split(">")[-1].replace("min",""))
            elif "-" in rt:
                low, high = rt.split("-")
                rt_gte, rt_lte = int(low.replace("min","")), int(high.replace("min",""))
            if rt_gte is not None:    
                    
            # Call TMDb discover API
                raw = list(discover.discover_movies(discover_params))[:n]
            for movie in raw:
                # Fetch full details to get runtime
                details = get_movie_details(getattr(movie, 'id', None))
                genres = [self.id_to_genre.get(g, "Unknown") for g in getattr(movie, 'genre_ids', [])]
                release_date = getattr(movie, 'release_date', 'N/A')
                # Extract year if possible
                year = release_date[:4] if release_date and len(release_date) >= 4 else "N/A"
                runtime = details.get('runtime', None)
                runtime_str = f"{runtime} mins" if runtime else "N/A"
                output.append(
                    f"\U0001F3AC {getattr(movie, 'title', '?')} ({year})\n"
                    f"\u2B50 {getattr(movie, 'vote_average', '?')}/10 | \u23F3 {runtime_str}\n"
                    f"\U0001F3F7\uFE0F {', '.join(genres)}\n"
                    f"\U0001F4D6 {getattr(movie, 'overview', 'No description')}\n"
                )
        return "\n".join(output) or "No recommendations found."