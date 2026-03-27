import os
import json
import shutil
import tempfile
import asyncio

from huggingface_hub import hf_hub_download
from google.genai import types
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from ..mcp_client import call_mcp_tool

TARGET_DATASET = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

async def image_downloader(repo_id: str, file_name: str) -> str:
    try:
        await asyncio.sleep(1.0)
        # Offload synchronous download to a background thread so the Telegram UI doesn't freeze
        path = await asyncio.to_thread(
            hf_hub_download, repo_id=repo_id, filename=f"images/{file_name}", repo_type="dataset"
        )
        safe_path = os.path.join(tempfile.gettempdir(), os.path.basename(path))
        shutil.copy2(path, safe_path)
        return safe_path
    except Exception as e:
        # HARD ABORT: Prevent pipeline from proceeding with no image
        raise RuntimeError(f"FATAL: Image download failed. Aborting pipeline. Details: {str(e)}")

async def mcp_taxonomy_fetcher() -> dict:
    try:
        authors = await call_mcp_tool("igbo-archives", "list_authors", {})
        categories = await call_mcp_tool("igbo-archives", "list_categories", {})
        return {"authors": authors.get("results", []), "categories": categories.get("results", [])}
    except Exception as e:
        return {"error": f"Taxonomy fetch failed - {str(e)}"}

async def process_hf_row(index: int) -> dict:
    """Extracts the RAW, unadulterated metadata from Hugging Face."""
    try:
        await asyncio.sleep(1.5)
        metadata_path = await asyncio.to_thread(
            hf_hub_download, repo_id=TARGET_DATASET, filename="data.jsonl", repo_type="dataset"
        )
        record = None
        
        with open(metadata_path, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i == index:
                    record = json.loads(line)
                    break
        
        if not record: 
            raise ValueError(f"FATAL: Record not found at index {index}. Aborting pipeline.")
        
        # WE PASS THE FULL, UNTRUNCATED METADATA DICTIONARY
        metadata = record.get("metadata", {})
        
        images = record.get("images", [])
        file_name = images[0].get("file_name") if images else ""
        
        image_local_path = ""
        if file_name:
            image_local_path = await image_downloader(TARGET_DATASET, file_name)
        else:
            raise ValueError("FATAL: No image found in the Hugging Face record. Vision agent cannot proceed.")
            
        return {
            "raw_metadata": record, 
            "image_path": image_local_path
        }
    except Exception as e:
        # Re-raise to ensure the agent orchestrator catches the hard stop
        raise RuntimeError(f"PIPELINE ABORTED: {str(e)}")


data_fetcher = Agent(
    name="data_fetcher",
    model=LiteLlm(
        model="groq/moonshotai/kimi-k2-instruct",
        api_key=GROQ_API_KEY,
        fallbacks=["groq/openai/gpt-oss-120b", "groq/meta-llama/llama-3.3-70b-versatile"]
    ), 
    description="Agent A1: Raw Metadata Retrieval from Hugging Face.",
    tools=[process_hf_row],
    instruction="""
ROLE: You are an Elite Archival Data Extractor.
GOAL: Retrieve a specific historical record and prepare it for the pipeline.
AVAILABLE DATA: Target Row Index: {current_index}
STRICT RULES:
1. DO NOT hallucinate, summarize, or alter the JSON payload returned by your tool.
2. You MUST dump the entire response payload VERBATIM into your final response so the next agent can read it.
TOOL MANDATE: Call the `process_hf_row` tool exactly once using the {current_index}.
"""
)

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
