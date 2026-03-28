import os
import asyncio
from ddgs import DDGS
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# Make sure we can expose the agent when importing this folder
__all__ = ["researcher"]

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

research_model = LiteLlm(
    model="groq/llama-3.3-70b-versatile", 
    api_key=GROQ_API_KEY,
    fallbacks=["groq/moonshotai/kimi-k2-instruct", "groq/moonshotai/kimi-k2-instruct-0905"]
)

async def duckduckgo_web_search(query: str) -> str:
    """Searches the internet for historical and geographical context."""
    try:
        # Run synchronous DDGS in a thread to avoid blocking the async event loop
        def _search():
            results = DDGS().text(query, max_results=3)
            # DDGS might return a generator or a list depending on version, so list() it
            results = list(results)
            if not results:
                return "No results found."
            return "\n\n".join([f"Source: {r.get('title', '')}\nSnippet: {r.get('body', '')}" for r in results])
            
        return await asyncio.to_thread(_search)
    except Exception as e:
        return f"Search failed: {str(e)}"

researcher = Agent(
    name="context_researcher",
    model=research_model,
    description="Agent: Researches geographical, historical, and cultural context on the internet.",
    tools=[duckduckgo_web_search],
    output_key="research_context", 
    instruction="""
ROLE:
You are an Elite Historical & Geographical Researcher for the Igbo Archives.

GOAL:
Read the raw_metadata and vision_report currently in the session state. 
RAW HF METADATA: {raw_metadata}
VISION REPORT: {vision_report}

Identify missing context (like modern geographical locations, historical background on the subject, or cultural significance) and search the internet to find it.

STRICT RULES:
1. Formulate ONE highly specific search query using the `duckduckgo_web_search` tool based on the available metadata above.
2. After getting the search results, write a concise summary of the historical, geographical, and cultural facts you discovered.
3. DO NOT invent information. Only summarize what the search tool returns.
4. If the search tool fails or returns nothing, just output: "No additional internet context found."
"""
)

