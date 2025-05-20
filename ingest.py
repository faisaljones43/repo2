#!/usr/bin/env python3
import os
import json
from tmdb_clients   import fetch_movies, save_movies_to_file
from vector_store   import MovieVectorStore

CHROMA_DIR = os.getenv("CHROMA_DIR", "./chroma_db")
MOVIES_FILE = os.getenv("MOVIES_FILE", "movies.json")
TMDB_PAGES = int(os.getenv("TMDB_PAGES", "5"))

def load_or_fetch_movies(path: str, pages: int):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            movies = json.load(f)
        print(f"📂 Loaded {len(movies)} movies from {path}")
    else:
        save_movies_to_file(path, pages)  
        with open(path, encoding="utf-8") as f:
            movies = json.load(f)
    return dedupe(movies)

def dedupe(movies: list[dict]) -> list[dict]:
    seen, unique = set(), []
    for m in movies:
        mid = str(m["id"])
        if mid not in seen:
            seen.add(mid)
            unique.append(m)
    print(f"🏷️  {len(unique)} unique movies after de-duplication")
    return unique

def main():
    movies = load_or_fetch_movies(MOVIES_FILE, TMDB_PAGES)

    print("🚀 Ingesting into vector store…")
    store = MovieVectorStore(persist_dir=CHROMA_DIR)
    store.ingest(movies_json=MOVIES_FILE, pages=TMDB_PAGES)
    print(f"✅ Done! Ingested {len(movies)} movies into '{store.col.name}'")

if __name__ == "__main__":
    main()
