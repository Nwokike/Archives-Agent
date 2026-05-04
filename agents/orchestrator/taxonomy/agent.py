import json
from typing import AsyncGenerator
from google.genai import types
from google.adk.agents import Agent
from google.adk.models import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from ..mcp_client import call_mcp_tool

class BypassLlm(BaseLlm):
    """A mock LLM that does nothing, used for purely programmatic agents."""
    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        yield LlmResponse(text="Bypass", model="bypass")

async def mcp_taxonomy_fetcher() -> dict:
    """Fetches and flattens authors and categories from the Igbo Archives MCP server."""
    try:
        authors = await call_mcp_tool("igbo-archives", "list_authors", {})
        categories = await call_mcp_tool("igbo-archives", "list_categories", {})
        
        if "error" in authors:
            raise ValueError(f"Authors API Error: {authors['error']}")
        if "error" in categories:
            raise ValueError(f"Categories API Error: {categories['error']}")
            
        # Flatten to simple lists of names for the writer
        author_names = [a.get("name") for a in authors.get("results", []) if a.get("name")]
        category_names = [c.get("name") for c in categories.get("results", []) if c.get("name")]
        
        return {
            "authors": author_names, 
            "categories": category_names
        }
    except Exception as e:
        # Return empty lists on failure to prevent pipeline breakage
        return {"authors": [], "categories": [], "error": str(e)}

async def fetch_taxonomy_programmatically(**kwargs) -> types.Content:
    """Programmatically provides live taxonomy data to the next agent."""
    taxonomies = await mcp_taxonomy_fetcher()
    return types.Content(
        role="model",
        parts=[types.Part.from_text(
            text=f"LIVE TAXONOMY DATA (For Synthesis Writer):\n{json.dumps(taxonomies, indent=2)}"
        )]
    )

taxonomy_mapper = Agent(
    name="taxonomy_mapper",
    model=BypassLlm(model="bypass"),
    description="Agent A2: Deterministic taxonomy dumping.",
    before_agent_callback=fetch_taxonomy_programmatically,
    instruction="Programmatic agent. Bypasses LLM."
)
