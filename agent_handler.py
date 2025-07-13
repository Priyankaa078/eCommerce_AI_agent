import os
from openai import OpenAI
import asyncio
from agents import Agent, Runner, function_tool
from dotenv import load_dotenv

# Load the API key from .env file
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define a function tool
@function_tool
def get_greeting(name: str) -> str:
    """Returns a friendly greeting to the user."""
    return f"Hello, {name}! 👋 I'm your AI assistant."

# Create an agent
agent = Agent(
    name="HelpfulAssistant",
    instructions="You're a helpful assistant that can answer questions and greet users.",
    tools=[get_greeting],
    model="gpt-4o"
)


# Interface to ask the agent
async def ask_agent(prompt: str) -> str:
   result = await Runner.run(agent , prompt)
   return result.final_output.strip() if result.final_output else "No response generated."
