import json
import os 

from typing import Annotated
import asyncio

from dotenv import load_dotenv

from IPython.display import display, HTML
from tmdbv3api import TMDb, Genre
from openai import AsyncOpenAI
from tmdbv3api import TMDb
from semantic_kernel.agents import ChatCompletionAgent, ChatHistoryAgentThread
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from semantic_kernel.contents import FunctionCallContent, FunctionResultContent, StreamingTextContent
from semantic_kernel.functions import kernel_function
from tmdbv3api import TMDb, Discover
from tmdbv3api import Movie
import pandas as pd
from datetime import datetime
from tmdbv3api import TMDb, Discover
import os, json
from tmdbv3api import TMDb, Genre, Discover
import semantic_kernel as sk
import random
import os
import json
from dotenv import load_dotenv
from tmdbv3api import TMDb, Genre, Discover
from semantic_kernel.functions import kernel_function

load_dotenv()
# Initialize TMDb with your API key
tmdb = TMDb()
tmdb.api_key ='2fa30f6a1d22eb80c6dc9cac9cc67bdc'
# Fetch the official list of movie genres
genre_client = Genre()
all_genres = genre_client.movie_list()

# Build a name→ID lookup (lowercased keys)
GENRE_MAP = {g.name.lower(): g.id for g in all_genres}

# Create a Discover instance for querying movies
discover = Discover()


# ─── Configuration ─────────────────────────────────────────────────────────

load_dotenv()  # look for .env in cwd

tmdb = TMDb()
tmdb.api_key = os.environ["TMDB_API_KEY"]   
  
# Build a lowercase name→id map of every genre
genre_client = Genre()
_all = genre_client.movie_list()
GENRE_MAP = {g.name.lower(): g.id for g in _all}

# A Discover client to fetch movies by genre, popularity, etc.
discover = Discover()
movie_api = Movie()

# ─── The Plugin Skill Class ─────────────────────────────────────────────────

class MovieTinderPlugin:
    @kernel_function(
        description=" Ask the user an list all available genres for the user to choose from"
    )
    def list_genres(self) -> str:
        """
        Returns a plain‐text list of all genres (pulled from GENRE_MAP)
        so the UI can display them for the user to pick one.
        """
        lines = ["Please choose from the following genres:"]
        for name in GENRE_MAP.keys():
            lines.append(f" • {name.title()}")
        return "\n".join(lines)
    
    @kernel_function(description="Ask the user what mood they want")
    def ask_mood(self) -> str:
        return "What kind of mood? (e.g. lighthearted, intense, adventurous)"

    @kernel_function(description="Ask the user for a preferred decade")
    def ask_decade(self) -> str:
        return "Which decade do you prefer? (e.g. 1980s, 1990s, 2000s)"

    @kernel_function(description="Ask if they want blockbusters or hidden gems")
    def ask_popularity(self) -> str:
        return "Do you lean toward popular hits or hidden gems?"

    @kernel_function(description="Ask for a runtime range")
    def ask_runtime(self) -> str:
        return "Any runtime preference? (e.g. < 90 min, 90–120 min, > 120 min)"
    
    @kernel_function(description="Show a numbered list and ask which excite them most")
    def present_options(self, movies_json: str) -> str:
        # 1) Try to parse JSON
        try:
            movies = json.loads(movies_json)
        except json.JSONDecodeError:
            return "Sorry, I couldn't parse the list of movies."

        # 2) Make sure it's actually a list
        if not isinstance(movies, list) or len(movies) == 0:
            return "Sorry, I couldn't find any movies to present."

        # 3) Build the prompt, safely pulling out title/year
        lines = ["Which of these sounds most exciting? Reply with numbers (e.g. 1,3):"]
        for i, m in enumerate(movies, start=1):
            if isinstance(m, dict):
                title = m.get("title", "Unknown title")
                year  = m.get("release_year", "")
            else:
                # fallback if m is somehow not a dict
                title = str(m)
                year  = ""
            lines.append(f"{i}. {title} ({year})")

        return "\n".join(lines)
    @kernel_function(
        description="Return tailored movie recommendations based on genre, mood, decade, popularity preference, and runtime"
    )
    def recommend_by_preferences(
        self,
        genre: str,
        mood: str,
        decade: str,
        popularity: str,
        runtime: str,
        top_n: str = "5"
    ) -> str:
        # 1) Parse top_n
        try:
            n = max(1, int(top_n))
        except ValueError:
            n = 5

        # 2) Genre → TMDb ID
        gid = GENRE_MAP.get(genre.strip().lower())
        if not gid:
            return "I couldn’t find that genre—please try again."

        # 3) Decade → date filters
        dec = decade.strip().lower()
        year_start, year_end = None, None
        if dec.endswith("s") and dec[:-1].isdigit():
            ys = int(dec[:-1])
            year_start, year_end = ys, ys + 9

        # 4) Runtime → runtime filters
        rt = runtime.replace(" ", "")
        rt_gte = rt_lte = None
        if "<" in rt:
            rt_lte = int(rt.split("<")[-1].replace("min",""))
        elif ">" in rt:
            rt_gte = int(rt.split(">")[-1].replace("min",""))
        elif "-" in rt:
            low, high = rt.split("-")
            rt_gte, rt_lte = int(low.replace("min","")), int(high.replace("min",""))

        # 5) Popularity → sort_by
        sort_by = "popularity.desc"
        if "hidden" in popularity.lower():
            sort_by = "vote_average.desc"

        # 6) Build discover params
        params = {
            "with_genres":    gid,
            "sort_by":        sort_by,
            "page":           1
        }
        if year_start and year_end:
            params["primary_release_date.gte"] = f"{year_start}-01-01"
            params["primary_release_date.lte"] = f"{year_end}-12-31"
        if rt_gte is not None:
            params["with_runtime.gte"] = rt_gte
        if rt_lte is not None:
            params["with_runtime.lte"] = rt_lte

        # 7) Fetch & trim
        raw = list(discover.discover_movies(params))[:n]

        # 8) Build human-readable bullets
        header = (
            f"Here are your top {n} {mood} "
            f"{decade} {popularity} {genre.title()} picks "
            f"(runtime {runtime}):"
        )
        lines = [header]
        for m in raw:
            year = (m.release_date or "").split("-")[0]
            overview = (m.overview or "").strip()
            lines.append(f" • {m.title} ({year}) — {overview}")

        return "\n".join(lines)