import os
import asyncio
from duckduckgo_search import DDGS
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# Make sure we can expose the agent when importing this folder
__all__ = ["researcher"]

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

research_model = LiteLlm(
    model="groq/llama-3.3-70b-versatile", 
    api_key=GROQ_API_KEY,
    fallbacks=["groq/moonshotai/kimi-k2-instruct", "groq/llama-3.1-8b-instant"]
)

async def duckduckgo_web_search(query: str) -> str:
    """Searches the internet for historical and geographical context."""
    try:
        # Run synchronous DDGS in a thread to avoid blocking the async event loop
        def _search():
            results = DDGS().text(query, max_results=5)
            # DDGS might return a generator or a list depending on version, so list() it
            results = list(results)
            if not results:
                return "No results found."
            import json
            return json.dumps(results, indent=2)
            
        return await asyncio.to_thread(_search)
    except Exception as e:
        return f"Search failed: {str(e)}"

def get_researcher_instruction(ctx) -> str:
    import json
    raw_md = ctx.state.get("raw_metadata", {})
    vision = ctx.state.get("vision_report", "No vision report available.")
    
    try:
        raw_str = json.dumps(raw_md, indent=2)
    except Exception:
        raw_str = str(raw_md)
        
    return f"""
ROLE:
You are an Elite Historical & Geographical Researcher for the Igbo Archives.

GOAL:
Here is the EXCLUSIVE raw data from Hugging Face you MUST analyze:
{raw_str}

Here is the Vision Analyst Report:
{vision}

Identify missing context (like modern geographical locations, historical background on the subject, or cultural significance) and search the internet to find it.

STRICT RULES:
1. Formulate ONE highly specific search query using the `duckduckgo_web_search` tool based on the available metadata above.
2. Under NO circumstances should you summarize or analyze the results in your final output.
3. Your FINAL OUTPUT MUST BE EXACTLY the raw JSON search results provided by the `duckduckgo_web_search` tool—nothing else. Outputting every single result provides maximum context to the next agent in the pipeline.
4. If the search tool fails or returns nothing, just output: "No additional internet context found."
"""

researcher = Agent(
    name="context_researcher",
    model=research_model,
    description="Agent: Researches geographical, historical, and cultural context on the internet.",
    tools=[duckduckgo_web_search],
    output_key="research_context", 
    instruction=get_researcher_instruction
)
