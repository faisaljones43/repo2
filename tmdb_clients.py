import os
import json
import requests
import time  # Added missing import
from datetime import datetime

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

def fetch_movies(pages: int = 5) -> list[dict]:
    """Fetch the top movies via TMDb discover, across `pages` pages."""
    movies = []
    for page in range(1, pages + 1):
        discover_resp = requests.get(
            f"{BASE_URL}/discover/movie",
            params={
                "api_key": API_KEY,
                "page": page,
                "language": "en-US",
                "sort_by": "popularity.desc"
            }
        ).json()
        
        # Process each movie in the current page
        for base_movie in discover_resp.get("results", []):
            # Get full details for each movie
            details = requests.get(
                f"{BASE_URL}/movie/{base_movie['id']}",
                params={"api_key": API_KEY}
            ).json()
            
            time.sleep(0.2)  
            
             
            timestamp = None
            try:
                rd = details.get("release_date")
                if rd:
                    rd_int = datetime.strptime(rd, "%Y-%m-%d")
                    timestamp = int(rd_int.timestamp())
            except (ValueError, TypeError):
                pass  # Keep timestamp as None if parsing fails
            
            movies.append({
                "id": str(details["id"]),  
                "genre_ids": [g["id"] for g in details.get("genres", [])],
                "title": details.get("title", ""),
                "overview": details.get("overview", ""),
                "poster_path": details.get("poster_path"),
                "release_date": timestamp,
                "vote_average": details.get("vote_average"),
                "popularity": details.get("popularity"),
                "runtime": details.get("runtime", 0)  
            })
    
    return movies

def save_movies_to_file(path: str = "movies.json", pages: int = 5) -> None:
    """Fetch and write movies.json (for one-off data dumps)."""
    movies = fetch_movies(pages)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(movies)} movies to {path}")

def get_movie_details(movie_id: int) -> dict:
    """Fetch full details for a single TMDb movie by its ID."""
    resp = requests.get(
        f"{BASE_URL}/movie/{movie_id}",
        params={
            "api_key": API_KEY,
            "language": "en-US"
        }
    ).json()
    return {
        "title": resp.get("title"),
        "overview": resp.get("overview"),
        "release_date": resp.get("release_date"),
        "vote_average": resp.get("vote_average"),
        "runtime": resp.get("runtime", 0)  
    }

if __name__ == "__main__":
    save_movies_to_file()