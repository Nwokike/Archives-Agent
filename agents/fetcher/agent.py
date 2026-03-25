import os
import json
import shutil
import tempfile

# Third-party & ADK Imports
from huggingface_hub import hf_hub_download
from google.genai import types
from google.adk.agents import Agent
from typing import Any
from google.adk.models.lite_llm import LiteLlm

# Local Imports
from agents.mcp_client import call_mcp_tool

# --- Configuration & Constants ---
TARGET_DATASET = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


# --- Tools ---

async def image_downloader(repo_id: str, file_name: str) -> str:
    """Downloads a dataset image to local temp storage to ensure availability."""
    try:
        path = hf_hub_download(repo_id=repo_id, filename=f"images/{file_name}", repo_type="dataset")
        
        # Isolate from HF cache to prevent corruption on deletion (Windows safe)
        safe_path = os.path.join(tempfile.gettempdir(), os.path.basename(path))
        shutil.copy2(path, safe_path)
        return safe_path
    
    except Exception as e:
        return f"ERROR: Image download failed - {str(e)}"


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
        return {"error": f"Taxonomy fetch failed - {str(e)}"}


async def process_hf_row(index: int) -> dict:
    """Extracts raw metadata from Hugging Face and maps it to the internal pipeline schema."""
    try:
        metadata_path = hf_hub_download(repo_id=TARGET_DATASET, filename="data.jsonl", repo_type="dataset")
        record = None
        
        # Read JSONL line by line to find the requested index
        with open(metadata_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i == index:
                    record = json.loads(line)
                    break
        
        if not record: 
            return {"error": f"Record not found at index {index}"}
        
        metadata = record.get("metadata", {})
        images = record.get("images", [])
        file_name = images[0].get("file_name") if images else ""
        
        # Download image now to ensure vision agents have local access
        image_local_path = ""
        if file_name:
            image_local_path = await image_downloader(TARGET_DATASET, file_name)
            
        return {
            "raw_metadata": metadata,
            "original_identity_number": metadata.get("idno"),
            "original_url": record.get("source_url"),
            "image_path": image_local_path
        }
        
    except Exception as e:
        return {"error": f"HF processing failed - {str(e)}"}


# --- Agents ---

# 1. Data Fetcher Agent (LLM-Driven)
data_fetcher = Agent(
    name="data_fetcher",
    model=LiteLlm(
        model="groq/moonshotai/kimi-k2-instruct",
        api_key=GROQ_API_KEY
    ), 
    description="Agent A1: Raw Metadata Retrieval from Hugging Face.",
    tools=[process_hf_row],
    instruction="""
    You are the 'data_fetcher'. Your sole mission is to retrieve specific records from Hugging Face.
    
    AUTONOMOUS CONTEXT:
    - Target Row Index: {current_index}
    
    WORKFLOW:
    1. Use 'process_hf_row' with the index {current_index} to get the raw record and image.
    2. You MUST dump the entire response payload VERBATIM. Do not summarize, format, or truncate the metadata.
    """
)

# 2. Taxonomy Mapper Agent (Programmatic / Zero-LLM)
async def fetch_taxonomy_programmatically(**kwargs) -> types.Content:
    """Circuit breaker callback to fetch taxonomy without invoking an LLM."""
    taxonomies = await mcp_taxonomy_fetcher()
    return types.Content(
        role="model",
        parts=[types.Part.from_text(
            text=f"LIVE TAXONOMY DATA (For Synthesis Writer to resolve entities):\n{json.dumps(taxonomies, indent=2)}"
        )]
    )

taxonomy_mapper = Agent(
    name="taxonomy_mapper",
    # Using a dummy model configuration to ensure no accidental API calls/charges occur
    model=LiteLlm(model="mock-model-bypass", api_key="dummy-key"),
    description="Agent A2: Deterministic taxonomy dumping (No LLM).",
    before_agent_callback=fetch_taxonomy_programmatically,
    instruction="This agent is programmatic. The framework will intercept execution via the callback and skip the LLM."
)