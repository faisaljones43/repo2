import os, json
from chromadb import PersistentClient
from openai import OpenAI
from tmdb_clients import fetch_movies

class MovieVectorStore:
    def __init__(self, persist_dir: str = "./chroma_db"):
        self.openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.client = PersistentClient(path=persist_dir)
        self.col    = self._get_or_create("movie_docs")
        self.id2movie: dict[str, dict] = {}
        
    def _get_or_create(self, name: str):
        if name in self.client.list_collections():
            return self.client.get_collection(name)
        return self.client.create_collection(name)

    def ingest(self,
               *,
               movies_json: str = "movies.json",
               pages: int        = 5,
               overwrite: bool   = True):
        """Fetch (or load) movies.json, dedupe, embed & persist."""

        if os.path.exists(movies_json):
            with open(movies_json, "r", encoding="utf-8") as f:
                movies = json.load(f)
            print(f"📂 Loaded {len(movies)} movies from {movies_json}")
        else:
            movies = fetch_movies(pages)
            with open(movies_json, "w", encoding="utf-8") as f:
                json.dump(movies, f, indent=2)
            print(f"🔄 Fetched & saved {len(movies)} movies to {movies_json}")

        seen, unique = set(), []
        for m in movies:
            mid = str(m["id"])
            if mid not in seen:
                seen.add(mid)
                unique.append(m)
        movies = unique
        print(f"🏷️  {len(movies)} unique movies after de-duplication")

        self.id2movie = { str(m["id"]): m for m in movies }

        if overwrite and self.col.name in self.client.list_collections():
            self.client.delete_collection(self.col.name)
            self.col = self._get_or_create(self.col.name)

        texts = [
            (m.get("overview") or m.get("title","")).strip()
            for m in movies
            if (m.get("overview") or m.get("title","")).strip()
        ]
        print("Sample overview types:", {type(t) for t in texts})
        print("Empty overviews:", sum(1 for t in texts if not t))

        resp = self.openai.embeddings.create(
            model="text-embedding-ada-002",
            input=texts
        )
        embeddings = resp.data

        
        self.col.add(
            ids=[ str(m["id"]) for m in movies ],
            embeddings=[ e.embedding for e in embeddings ],
            documents=texts,
            metadatas=[
                    {
                        "id":           (m["id"]),
                        "genre_ids":    str(m.get("genre_ids", [])),
                        "release_year": (
                            int(str(m.get("release_date", "0000")).split("-")[0])
                            if m.get("release_date") else 0
                        ),
                        "popularity":   m.get("popularity", 0.0),
                        "runtime":      m.get("runtime", 0)
                    }
                for m in movies
            ]
        )
        print(f"✅ Ingested {len(movies)} docs into '{self.col.name}'")
        print("🔍 Documents in Chroma now:", self.col.count())  #should be 96
        try:
            self.client.persist()
        except Exception:
            pass

    def search(self,
           query: str,
           top_n: int   = 5,
           filters: dict = None
) -> list[dict]:
        embed_resp = self.openai.embeddings.create(
            model="text-embedding-ada-002",
            input=[query]
        )
        query_embedding = embed_resp.data[0].embedding
        print(f"🔍 Query embedding length: {len(query_embedding)}")  

        query_resp = self.col.query(
            query_embeddings=[query_embedding],
            n_results=top_n,
            where=filters or {}
        )
        # Debug the raw response
        print("🔍 Chroma raw ids:",   query_resp["ids"])
        if "distances" in query_resp:
            print("🔍 Chroma distances:", query_resp["distances"])

        # 3) Turn IDs into movies
        ids = query_resp["ids"][0]
        results = [self.id2movie[mid] for mid in ids if mid in self.id2movie]
        print("🔍 Mapped back to movies:", [m["title"] for m in results])
        return results