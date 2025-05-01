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
tmdb.api_key ='b8ea91b6eba21bb13dbf93dbab0a8d1a'
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
        description="List all available genres for the user to choose from"
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
    @kernel_function(description="Return top N movies for a genre as a JSON array")
    def recommend_by_genre(self, genre: str, top_n: str = "5") -> str:
        name = genre.strip().lower()
        gid = GENRE_MAP.get(name)
        if gid is None:
            return json.dumps([])

        try:
            n = int(top_n)
        except ValueError:
            n = 5

        # fetch the list
        raw = list(discover.discover_movies({
            "with_genres": gid,
            "sort_by":     "popularity.desc",
            "page":        1
        }))[:n]

        # serialize to JSON
        recs = []
        for m in raw:
            recs.append({
                "id":            m.id,
                "title":         m.title,
                "release_year":  (m.release_date or "").split("-")[0],
                "overview":      m.overview or "",
                "popularity":    m.popularity,
                "vote_average":  m.vote_average
            })
        return json.dumps(recs)
    @kernel_function(description="Show a numbered list and ask which excite them most")
    def present_options(self, movies_json: str) -> str:
        movies = json.loads(movies_json)
        if not movies:
            return "Sorry, I couldn't find any movies in that genre."
        lines = ["Which of these sounds most exciting? Reply with numbers (e.g. 1,3):"]
        for i, m in enumerate(movies, start=1):
            lines.append(f"{i}. {m['title']} ({m['release_year']})")
        return "\n".join(lines)
    
  