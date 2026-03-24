import os
import json
from google_adk import SequentialAgent
from huggingface_hub import hf_hub_download
from mcp import call_tool as mcp_call_tool
from ..schema import PipelineState

class FetcherAgent(SequentialAgent):
    """Agent A: Fetches Row Metadata from HF and Live Taxonomies."""
    model = "gemini-2.5-flash-lite"
    
    async def step_fetch_metadata(self, state: PipelineState):
        try:
            metadata_path = hf_hub_download(repo_id=state.repo_id, filename="data.jsonl", repo_type="dataset")
            with open(metadata_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i == state.current_index:
                        state.hf_metadata = json.loads(line)
                        return True
            return False
        except: return False

    async def step_download_image(self, state: PipelineState):
        try:
            images = state.hf_metadata.get("images", [])
            if not images: return False
            file_name = images[0].get("file_name")
            state.image_path = hf_hub_download(repo_id=state.repo_id, filename=f"images/{file_name}", repo_type="dataset")
            return True
        except: return False

    async def step_fetch_taxonomies(self, state: PipelineState):
        try:
            authors_resp = await mcp_call_tool("igbo-archives", "list_authors", {})
            categories_resp = await mcp_call_tool("igbo-archives", "list_categories", {})
            state.taxonomies["authors"] = authors_resp.get("results", [])
            state.taxonomies["categories"] = categories_resp.get("results", [])
            return True
        except: return False
