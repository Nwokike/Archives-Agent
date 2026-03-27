import os
import json
import shutil
import tempfile
import asyncio
from typing import Dict, Any, Optional

from huggingface_hub import hf_hub_download
from google.adk.agents import Agent, Context, SequentialAgent
from google.adk.models.lite_llm import LiteLlm

# --- Local Sub-Agent Imports ---
from .taxonomy.agent import taxonomy_mapper
from .vision.agent import vision
from .synthesis.agent import synthesis_loop
from .publisher.agent import publisher

# --- Configuration & Constants ---
TARGET_DATASET = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# --- Helper Functions (Not exposed to LLM) ---

async def _download_image(repo_id: str, file_name: str) -> str:
    """Internal helper to download an image from Hugging Face without blocking."""
    await asyncio.sleep(1.0) # Rate limit buffering
    path = await asyncio.to_thread(
        hf_hub_download, repo_id=repo_id, filename=f"images/{file_name}", repo_type="dataset"
    )
    safe_path = os.path.join(tempfile.gettempdir(), os.path.basename(path))
    shutil.copy2(path, safe_path)
    return safe_path

def _read_jsonl_record(filepath: str, target_index: int) -> Optional[Dict[str, Any]]:
    """Synchronous file reader to be executed in a separate thread."""
    with open(filepath, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i == target_index:
                return json.loads(line)
    return None


# --- Agent Tools ---

async def fetch_hf_record(ctx: Context, index: int) -> Dict[str, Any]:
    """
    Extracts the raw metadata and downloads the associated image from Hugging Face for a given row index.
    
    Args:
        ctx (Context): The ADK session context, injected automatically.
        index (int): The row index of the dataset to fetch.
        
    Returns:
        dict: A dictionary containing the 'raw_metadata' (dict) and the local 'image_path' (str).
              If an error occurs, returns a dictionary with an 'error' key.
    """
    try:
        await asyncio.sleep(1.5) # Rate limit buffering
        
        # 1. Download metadata file
        metadata_path = await asyncio.to_thread(
            hf_hub_download, repo_id=TARGET_DATASET, filename="data.jsonl", repo_type="dataset"
        )
        
        # 2. Extract specific record without blocking the event loop
        record = await asyncio.to_thread(_read_jsonl_record, metadata_path, index)
        
        if not record: 
            return {"error": f"Record not found at index {index}. It may exceed dataset bounds."}
        
        # 3. Extract image metadata and download
        images = record.get("images", [])
        file_name = images[0].get("file_name") if images else ""
        
        if not file_name:
            return {"error": f"No image found in the Hugging Face record for index {index}."}
            
        image_local_path = await _download_image(TARGET_DATASET, file_name)
        
        # --- FIX: Save to global session state so downstream agents can access it ---
        ctx.state["image_path"] = image_local_path
        ctx.state["raw_metadata"] = record
            
        return {
            "raw_metadata": record, 
            "image_path": image_local_path
        }
        
    except Exception as e:
        return {"error": f"Failed to fetch HF record: {str(e)}"}


# --- Callbacks ---

def initialize_session_state(callback_context: Context):
    """Ensures critical state variables exist for template substitution in the prompt."""
    state = callback_context.state
    state.setdefault("current_index", 0)
    state.setdefault("dataset_id", TARGET_DATASET)


# --- Models & Agents ---

orchestrator_model = LiteLlm(
    model="groq/moonshotai/kimi-k2-instruct",
    api_key=GROQ_API_KEY,
    # RESILIENCE: Fallback chain of high-capacity Groq models
    fallbacks=["groq/openai/gpt-oss-120b", "groq/llama-3.3-70b-versatile"]
)

archive_pipeline = SequentialAgent(
    name="execute_archive_pipeline",
    sub_agents=[taxonomy_mapper, vision, synthesis_loop, publisher],
    description="The Master Archiving Pipeline. Executes taxonomy injection, analysis, synthesis, and publication."
)

orchestrator = Agent(
    name="orchestrator",
    model=orchestrator_model, 
    description="The root supervisor for the Igbo Archives Autonomous Ingestion System.",
    sub_agents=[archive_pipeline],
    tools=[fetch_hf_record],
    before_agent_callback=initialize_session_state,
    instruction="""
ROLE:
You are the Chief Orchestrator of the Igbo Archives Autonomous Ingestion System.

GOAL:
Your primary responsibility is to fetch the raw data from Hugging Face for a given row index and then trigger the `execute_archive_pipeline`.

STRICT WORKFLOW:
1. DATA FETCH: You MUST first call the `fetch_hf_record` tool using the Target Row Index ({current_index}).
2. STATE UPDATE: Verify the tool did not return an error. The returned metadata and image path are automatically tracked in the system.
3. PIPELINE TRIGGER: Call the `execute_archive_pipeline` agent to begin the archival process (Taxonomy -> Vision -> Synthesis -> Publisher).

AVAILABLE DATA:
- Target Dataset: {dataset_id}
- Current Unarchived Index: {current_index}

STRICT RULES:
1. If the user explicitly provides a row index (e.g., "Process row 5"), use it. Otherwise, use the Current Unarchived Index ({current_index}).
2. If the fetch tool returns an error, report it to the user and halt the pipeline.
3. Keep your responses clinical, professional, and brief.
4. Acknowledge missing data gracefully; do not invent details.
    """.strip()
)

root_agent = orchestrator