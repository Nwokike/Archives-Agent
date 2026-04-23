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
from .audio.agent import execute_audio_analysis
from .synthesis.agent import synthesis_loop
from .publisher.agent import publisher

# --- Configuration & Constants ---
from .config import DATASETS, DEFAULT_DATASET

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Helper Functions (Not exposed to LLM) ---

async def _download_media(repo_id: str, folder: str, file_name: str) -> str:
    """Internal helper to download media (image or audio) from Hugging Face."""
    await asyncio.sleep(1.0) # Rate limit buffering
    
    # Handle cases where the filename in JSON already includes the folder path
    target_filename = file_name if "/" in file_name else f"{folder}/{file_name}"
    
    path = await asyncio.to_thread(
        hf_hub_download, repo_id=repo_id, filename=target_filename, repo_type="dataset"
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

async def fetch_hf_record(ctx: Context, dataset_id: str, index: int) -> Dict[str, Any]:
    """
    Extracts raw metadata and dynamically downloads the associated media (image or audio) from HF.
    """
    try:
        await asyncio.sleep(1.5) 
        
        metadata_path = await asyncio.to_thread(
            hf_hub_download, repo_id=dataset_id, filename="data.jsonl", repo_type="dataset"
        )
        
        record = await asyncio.to_thread(_read_jsonl_record, metadata_path, index)
        if not record: 
            return {"error": f"Record not found at index {index}. It may exceed dataset bounds."}
        
        # 1. Check for Images First
        images = record.get("images", [])
        if images and isinstance(images, list) and len(images) > 0:
            file_name = images[0].get("file_name", "")
            if file_name:
                media_local_path = await _download_media(dataset_id, "images", file_name)
                
                # Save universal state
                ctx.state["media_path"] = media_local_path
                ctx.state["media_type"] = "image"
                ctx.state["raw_metadata"] = record
                
                return {"raw_metadata": record, "media_type": "image", "media_path": media_local_path}

        # 2. Check for Audio Second
        audio = record.get("audio", [])
        if audio:
            # Handle standard HF dict lists or raw strings
            if isinstance(audio, list) and len(audio) > 0:
                file_name = audio[0].get("file_name", audio[0].get("path", ""))
            elif isinstance(audio, str):
                file_name = audio
            else:
                file_name = ""
                
            if file_name:
                media_local_path = await _download_media(dataset_id, "audio", file_name)
                
                # Save universal state
                ctx.state["media_path"] = media_local_path
                ctx.state["media_type"] = "audio"
                ctx.state["raw_metadata"] = record
                
                return {"raw_metadata": record, "media_type": "audio", "media_path": media_local_path}
                
        # 3. Fallback for Pure Documents (No Media)
        ctx.state["media_path"] = None
        ctx.state["media_type"] = "document"
        ctx.state["raw_metadata"] = record
        
        return {"raw_metadata": record, "media_type": "document", "media_path": "NONE"}
        
    except Exception as e:
        return {"error": f"Failed to fetch HF record: {str(e)}"}


# --- Callbacks ---

def initialize_session_state(callback_context: Context):
    state = callback_context.state
    state.setdefault("current_index", 0)
    state.setdefault("dataset_id", DEFAULT_DATASET)


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
    # Notice both media tools are now provided to the orchestrator
    tools=[fetch_hf_record, execute_vision_analysis, execute_audio_analysis],
    before_agent_callback=initialize_session_state,
    instruction=f"""
ROLE:
You are the Chief Orchestrator of the Igbo Archives Autonomous Ingestion System.

GOAL:
Fetch raw data, dynamically route the media to the correct analyst (vision or audio), verify the report against the metadata, and trigger the pipeline.

STRICT WORKFLOW:
1. DATA FETCH: Call `fetch_hf_record`.
   - If the user provides a SYSTEM DIRECTIVE containing a dataset name, you MUST use that dataset as the `dataset_id`.
   - If there is NO system directive (e.g., testing mode), you MUST fallback to using "{DEFAULT_DATASET}" as the `dataset_id`.
   
2. MEDIA ROUTING & ANALYSIS: Review the `media_type` returned by `fetch_hf_record`.
   - If `media_type` is "image": Call the `execute_vision_analysis` tool blind.
   - If `media_type` is "audio": Call the `execute_audio_analysis` tool blind.
   - If `media_type` is "document": Skip media analysis and move to VALIDATION.
   
3. VALIDATION: Cross-reference the raw HF metadata with the media analyst's unbiased report. 
   - If the media completely mismatches the HF record (e.g., the record says "wooden mask" but the image shows "modern clothing", or the record says "flute music" but the audio is "silence"), HALT the process entirely. Output an error explaining the mismatch to the user.
   
4. PIPELINE TRIGGER: If the media is valid, call the `execute_archive_pipeline` agent to begin the archival synthesis process.

AVAILABLE DATA:
- Fallback Dataset: {DEFAULT_DATASET}
- Current Unarchived Index: {{current_index}}

STRICT RULES:
1. If the user explicitly provides a row index (e.g., "Process row 5"), use it. Otherwise, use {{current_index}}.
2. Keep your direct responses to the user clinical, professional, and brief.
""".strip()
)

root_agent = orchestrator