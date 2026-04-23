import json

from google.genai import types
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from ..mcp_client import call_mcp_tool

async def mcp_taxonomy_fetcher() -> dict:
    try:
        authors = await call_mcp_tool("igbo-archives", "list_authors", {})
        categories = await call_mcp_tool("igbo-archives", "list_categories", {})
        
        if "error" in authors:
            raise ValueError(f"Authors API Error: {authors['error']}")
        if "error" in categories:
            raise ValueError(f"Categories API Error: {categories['error']}")
            
        return {"authors": authors.get("results", []), "categories": categories.get("results", [])}
    except Exception as e:
        raise RuntimeError(f"Taxonomy fetch completely failed - {str(e)}")

async def fetch_taxonomy_programmatically(**kwargs) -> types.Content:
    taxonomies = await mcp_taxonomy_fetcher()
    return types.Content(
        role="model",
        parts=[types.Part.from_text(
            text=f"LIVE TAXONOMY DATA (For Synthesis Writer):\n{json.dumps(taxonomies, indent=2)}"
        )]
    )

taxonomy_mapper = Agent(
    name="taxonomy_mapper",
    model=LiteLlm(model="mock-model-bypass", api_key="dummy-key"),
    description="Agent A2: Deterministic taxonomy dumping.",
    before_agent_callback=fetch_taxonomy_programmatically,
    instruction="Programmatic agent. Bypasses LLM."
)
