import os
import asyncio
from ddgs import DDGS
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

__all__ = ["researcher"]

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

research_model = LiteLlm(
    model="gemini/gemma-4-31b-it", 
    api_key=GEMINI_API_KEY,
    fallbacks=["gemini/gemma-4-26b-a4b-it"]
)

async def duckduckgo_web_search(query: str) -> str:
    """Searches the internet for historical, geographical, and cultural context."""
    try:
        def _search():
            # Increased to 5 to give the agent more raw snippets to choose from
            results = DDGS().text(query, max_results=5)
            results = list(results)
            if not results:
                return "No results found."
            # Now correctly captures and returns the URL link along with the snippet
            return "\n\n".join([f"Source: {r.get('title', '')}\nLink: {r.get('href', '')}\nSnippet: {r.get('body', '')}" for r in results])
            
        return await asyncio.to_thread(_search)
    except Exception as e:
        return f"Search failed: {str(e)}"

researcher = Agent(
    name="context_researcher",
    model=research_model,
    description="Agent: Gathers maximum supplemental context by performing targeted web searches based on metadata and vision reports.",
    tools=[duckduckgo_web_search],
    output_key="research_context", 
    instruction="""
ROLE: Elite Historical Researcher and Context Gatherer for the Igbo Archives.

GOAL: Gather as much highly specific supplemental context as possible using targeted web searches.

AVAILABLE DATA:
- RAW HF METADATA: {raw_metadata}
- VISION REPORT: {vision_report}

STRICT WORKFLOW:
1. ENTITY EXTRACTION: Identify specific Names, Dates, precise Locations, cultural terms (e.g., instruments, masquerades), or specific Events from the Metadata and Vision Report.
2. EXHAUSTIVE WEB SEARCH: Call `duckduckgo_web_search` multiple times if necessary. Build targeted queries using the exact entities extracted in step 1 to find historical, geographical, or cultural context.
3. FILTER: If the web search results DO NOT explicitly mention the specific entities you queried, discard those specific results.
4. OUTPUT: Output ALL the exact text/snippets caught from the searches, untouched and un-rewritten, with their Source Link/URLs.

STRICT RULES:
- NO REWRITING. Do not summarize. Provide verbatim text directly from the search snippets.
- NO GENERAL TRIVIA. If the search returns generic encyclopedia data about "The Igbo people", discard it. Focus on specifics related to the metadata.
- MAXIMIZE CONTEXT: Your goal is to find as many specific facts as possible to enrich the archive. Do not stop at just one search if more entities can be explored.
- If no specific entities exist to search, or searches yield nothing useful, output EXACTLY: "No specific supplemental context found."
""".strip()
)
