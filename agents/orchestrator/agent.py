import os
import json
import shutil
import tempfile
import asyncio
from typing import Dict, Any, Optional

from huggingface_hub import hf_hub_download
from google.adk.agents import Agent, Context, SequentialAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.agent_tool import AgentTool

# --- Local Sub-Agent Imports ---
from .research.agent import researcher
from .taxonomy.agent import taxonomy_mapper
from .vision.agent import execute_vision_analysis
from .synthesis.agent import synthesis_loop
from .publisher.agent import publisher

# --- Configuration & Constants ---
TARGET_DATASET = os.getenv("TARGET_DATASET", "nwokikeonyeka/maa-cambridge-south-eastern-nigeria")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

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
    """
    try:
        await asyncio.sleep(1.5) 
        
        metadata_path = await asyncio.to_thread(
            hf_hub_download, repo_id=TARGET_DATASET, filename="data.jsonl", repo_type="dataset"
        )
        
        record = await asyncio.to_thread(_read_jsonl_record, metadata_path, index)
        if not record: 
            return {"error": f"Record not found at index {index}. It may exceed dataset bounds."}
        
        images = record.get("images", [])
        file_name = images[0].get("file_name") if images else ""
        
        if not file_name:
            return {"error": f"No image found in the Hugging Face record for index {index}."}
            
        image_local_path = await _download_image(TARGET_DATASET, file_name)
        
        # Saves raw metadata directly to state
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
    state = callback_context.state
    state.setdefault("current_index", 0)
    state.setdefault("dataset_id", TARGET_DATASET)


# --- Models & Agents ---

orchestrator_model = LiteLlm(
    model="gemini/gemma-4-31b-it",
    api_key=GEMINI_API_KEY,
    fallbacks=["gemini/gemma-4-26b-a4b-it"]
)

archive_pipeline = SequentialAgent(
    name="execute_archive_pipeline",
    sub_agents=[researcher, taxonomy_mapper, synthesis_loop, publisher],
    description="The Master Archiving Pipeline. Executes taxonomy injection, synthesis, and publication."
)

orchestrator = Agent(
    name="orchestrator",
    model=orchestrator_model, 
    description="The root supervisor for the Igbo Archives Autonomous Ingestion System.",
    sub_agents=[archive_pipeline],
    tools=[fetch_hf_record, execute_vision_analysis],
    before_agent_callback=initialize_session_state,
    instruction="""
ROLE:
You are the Chief Orchestrator of the Igbo Archives Autonomous Ingestion System.

GOAL:
Fetch raw data, command the vision analyst to describe the image completely blind (no context), verify the image matches the record, and trigger the pipeline, if it does not match or no response, donot trigger and state the reason.

STRICT WORKFLOW:
1. DATA FETCH: Call `fetch_hf_record` using the Target Row Index ({current_index}). 
2. BLIND VISION ANALYSIS: Call the `vision_analyst` tool. You DO NOT need to give it any prompt or context, it is hardcoded to run blind. Wait for its report. (The report is automatically saved to the database).
3. VALIDATION: Cross-reference the raw HF metadata with the vision analyst's unbiased report. 
   - If the image completely mismatches the HF record or no response from the vision analyst (e.g., the record is for a wooden mask but the image shows modern clothing, or no image description, or no reply at all), HALT the process entirely. Output an error explaining the mismatch to the user.
4. PIPELINE TRIGGER: If the image is valid, call the `execute_archive_pipeline` agent to begin the archival synthesis process.

AVAILABLE DATA:
- Target Dataset: {dataset_id}
- Current Unarchived Index: {current_index}

STRICT RULES:
1. If the user explicitly provides a row index (e.g., "Process row 5"), use it. Otherwise, use {current_index}.
2. Keep your direct responses to the user clinical, professional, and brief.
""".strip()
)

root_agent = orchestrator