import asyncio
from agent import MoviePreferenceAgent
from langchain_core.messages import HumanMessage, AIMessage
async def run():
    ag = MoviePreferenceAgent()
    print("🎬 Welcome!\n")
    # ask questions
    while (q := ag.next_q()) is not None:
        ans = input(f"{q}\n> ").strip()
        if ans.lower() in ("quit","exit"): break
        ag.handle_answer(ans)
    # summary + recommend
    print("\nSummary:", ag.summary())
    print("\nRecommendations:\n", ag.recommend(
    ag.prefs.get("genre", ""),
    ag.prefs.get("mood", ""),
    ag.prefs.get("decade", ""),
    ag.prefs.get("popularity", ""),
    ag.prefs.get("runtime", "")
))

if __name__=="__main__":
    asyncio.run(run())
