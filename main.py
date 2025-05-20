import asyncio
from agent import MoviePreferenceAgent
from langchain_core.messages import HumanMessage, AIMessage

def get_user_id():
    user_id = input("Enter your username or email (for personalized recommendations): ").strip()
    if not user_id:
        user_id = "default"
    return user_id

async def run():
    while True:
        user_id = get_user_id()
        ag = MoviePreferenceAgent(user_id=user_id)
        print(f"\nWelcome, {user_id}!\n")
        mode = input("Would you like recommendations based on your previous answers (p), or try something new (n)? [p/n]: ").strip().lower()
        if mode == "p" and ag.prefs:
            # Use most recent preferences
            print("\nSummary:", ag.summary())
            print("\nRecommendations:\n", ag.recommend(
                ag.prefs.get("genre", ""),
                ag.prefs.get("mood", ""),
                ag.prefs.get("decade", ""),
                ag.prefs.get("popularity", ""),
                ag.prefs.get("runtime", "")
            ))
        else:
            # Ask questionnaire again
            ag.idx = 0
            while (q := ag.next_q()) is not None:
                ans = input(f"{q}\n> ").strip()
                if ans.lower() in ("quit", "exit"): return
                ag.handle_answer(ans)
            print("\nSummary:", ag.summary())
            print("\nRecommendations:\n", ag.recommend(
                ag.prefs.get("genre", ""),
                ag.prefs.get("mood", ""),
                ag.prefs.get("decade", ""),
                ag.prefs.get("popularity", ""),
                ag.prefs.get("runtime", "")
            ))
        again = input("\nWould you like to get more recommendations or try a different user? (y/n): ").strip().lower()
        if again != "y":
            break

if __name__=="__main__":
    asyncio.run(run())
