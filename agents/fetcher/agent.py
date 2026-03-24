import os
import json
import shutil
from google.adk.agents import Agent
from huggingface_hub import hf_hub_download
from agents.mcp_client import call_mcp_tool

# Tool: Downloads image to /tmp to avoid link rot
async def image_downloader(repo_id: str, file_name: str) -> str:
    """Downloads a dataset image to local /tmp storage to ensure availability."""
    try:
        path = hf_hub_download(repo_id=repo_id, filename=f"images/{file_name}", repo_type="dataset")
        # Isolate from HF cache to prevent corruption on deletion
        safe_path = os.path.join("/tmp", os.path.basename(path))
        shutil.copy2(path, safe_path)
        return safe_path
    except Exception as e:
        return f"ERROR: {str(e)}"

# Tool: Fetches live taxonomies from the archives server via MCP
async def mcp_taxonomy_fetcher() -> dict:
    """Gets live Authors and Categories from the Igbo Archives server."""
    try:
        authors = await call_mcp_tool("igbo-archives", "list_authors", {})
        categories = await call_mcp_tool("igbo-archives", "list_categories", {})
        return {
            "authors": authors.get("results", []),
            "categories": categories.get("results", [])
        }
    except Exception as e:
        return {"error": str(e)}

# Tool: Map HF Record to Pipeline Schema
async def process_hf_row(repo_id: str, index: int) -> dict:
    """Extracts raw metadata from HF and maps it to the internal pipeline schema."""
    try:
        metadata_path = hf_hub_download(repo_id=repo_id, filename="data.jsonl", repo_type="dataset")
        record = None
        with open(metadata_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i == index:
                    record = json.loads(line)
                    break
        
        if not record: return {"error": "Index out of bounds"}
        
        # Primary mapping: idno -> original_identity_number
        metadata = record.get("metadata", {})
        images = record.get("images", [])
        file_name = images[0].get("file_name") if images else ""
        
        # Download image now to ensure vision has access
        image_local_path = ""
        if file_name:
            image_local_path = await image_downloader(repo_id, file_name)
            
        return {
            "raw_metadata": metadata,
            "original_identity_number": metadata.get("idno"),
            "original_url": record.get("source_url"),
            "image_path": image_local_path
        }
    except Exception as e:
        return {"error": str(e)}

# Fetcher Agent
fetcher = Agent(
    name="fetcher_taxonomist",
    model="gemini-2.5-flash-lite", 
    description="Agent A: Metadata retrieval and taxonomy mapping.",
    tools=[process_hf_row, mcp_taxonomy_fetcher],
    instruction="""
    Use 'process_hf_row' to get the raw record and downloaded image path.
    Use 'mcp_taxonomy_fetcher' to get live server categories.
    Return all extracted data to the supervisor.
    """
)
