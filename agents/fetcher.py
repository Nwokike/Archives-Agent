import os
import json
from google_adk import SequentialAgent, AgentApp
from huggingface_hub import hf_hub_download
from mcp import call_tool as mcp_call_tool
from agents.schema import PipelineState

# --- Fetcher & Taxonomist Agent (Agent A) ---
class FetcherAgent(SequentialAgent):
    """
    Agent A: Fetches Row Metadata from HF and Live Taxonomies from Igbo Archives.
    Standard: Metadata-First deterministic row access.
    """
    model = "gemini-2.5-flash-lite"
    
    async def step_fetch_metadata(self, state: PipelineState):
        """1. Deterministic metadata fetch via data.jsonl."""
        try:
            print(f"⚙️ Fetcher: Downloading metadata for index {state.current_index}...")
            metadata_path = hf_hub_download(
                repo_id=state.repo_id, 
                filename="data.jsonl", 
                repo_type="dataset"
            )
            
            with open(metadata_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i == state.current_index:
                        state.hf_metadata = json.loads(line)
                        print(f"✅ Fetcher: Row {state.current_index} metadata cached.")
                        return True
            
            state.status = "error: index out of bounds"
            return False
        except Exception as e:
            state.status = f"error: {str(e)}"
            return False

    async def step_download_image(self, state: PipelineState):
        """2. Single image download to /tmp."""
        try:
            images = state.hf_metadata.get("images", [])
            if not images:
                return False
                
            file_name = images[0].get("file_name")
            if not file_name:
                return False
                
            print(f"📸 Fetcher: Downloading {file_name}...")
            state.image_path = hf_hub_download(
                repo_id=state.repo_id,
                filename=f"images/{file_name}",
                repo_type="dataset"
            )
            return True
        except Exception as e:
            state.status = f"error: image failed {str(e)}"
            return False

    async def step_fetch_taxonomies(self, state: PipelineState):
        """3. Fetch live Categories and Authors from MCP."""
        try:
            print("🌐 Fetcher: Fetching live taxonomies from MCP...")
            authors_resp = await mcp_call_tool("igbo-archives", "list_authors", {})
            categories_resp = await mcp_call_tool("igbo-archives", "list_categories", {})
            
            state.taxonomies["authors"] = authors_resp.get("results", [])
            state.taxonomies["categories"] = categories_resp.get("results", [])
            
            print(f"✅ Fetcher: Found {len(state.taxonomies['authors'])} authors and {len(state.taxonomies['categories'])} categories.")
            state.status = "fetched"
            return True
        except Exception as e:
            state.status = f"error: mcp taxonomy failed {str(e)}"
            return False
