from typing import Dict, List
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import StrOutputParser

# Define the questions
QUESTIONS = [
    "Would you like to see movies from a specific genre?",
    "What kind of mood? (e.g. lighthearted, intense, adventurous)",
    "Which decade do you prefer? (e.g. 1980s, 1990s, 2000s)",
    "Do you lean toward popular hits or hidden gems?",
    "Any runtime preference? (e.g. < 90 min, 90–120 min, > 120 min)"
]

QUESTION_KEYS = ["genre", "mood", "decade", "popularity", "runtime"]

class MoviePreferenceAgent:
    def __init__(self):
        self.preferences = {}
        self.current_question_index = 0
        self.llm = ChatOpenAI(temperature=0)
        self.output_parser = StrOutputParser()
        
        # Create the summary prompt
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful movie recommendation assistant. Create a friendly summary of the user's movie preferences."),
            ("human", "Here are the user's preferences:\n{preferences}\n\nPlease create a friendly summary of these preferences.")
        ])
        
        # Create the chain for summarization
        self.summary_chain = self.summary_prompt | self.llm | self.output_parser

    def get_next_question(self) -> str:
        """Get the next question to ask."""
        if self.current_question_index < len(QUESTIONS):
            return QUESTIONS[self.current_question_index]
        return None

    def process_answer(self, answer: str) -> str:
        """Process the user's answer and store it."""
        if self.current_question_index < len(QUESTIONS):
            self.preferences[QUESTION_KEYS[self.current_question_index]] = answer
            self.current_question_index += 1
            return self.get_next_question()
        return None

    def get_summary(self) -> str:
        """Generate a summary of the collected preferences."""
        if not self.preferences:
            return "No preferences collected yet."
            
        # Format preferences for the prompt
        preferences_text = "\n".join([
            f"{QUESTIONS[i]}\n→ {self.preferences[key]}"
            for i, key in enumerate(QUESTION_KEYS)
            if key in self.preferences
        ])
        
        # Generate summary using the LLM
        summary = self.summary_chain.invoke({"preferences": preferences_text})
        return summary

def main():
    # Create the agent
    agent = MoviePreferenceAgent()
    
    # Start the conversation
    print("Welcome to the Movie Preference Assistant!")
    print("I'll ask you a few questions to understand your movie preferences.\n")
    
    # Ask questions and collect answers
    while True:
        question = agent.get_next_question()
        if not question:
            break
            
        print(f"\nAgent: {question}")
        answer = input("You: ").strip()
        
        if answer.lower() in ['quit', 'exit', 'stop']:
            print("\nAgent: Conversation ended. Here's a summary of what we discussed:")
            break
            
        agent.process_answer(answer)
    
    # Generate and display summary
    summary = agent.get_summary()
    print("\nAgent: " + summary)

if __name__ == "__main__":
    main()
