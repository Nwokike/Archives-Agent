from pydantic import BaseModel, Field
from typing import Optional

def get_initial_state() -> dict:
    """
    The absolute source of truth for the ADK session memory.
    Ensures all variables are initialized before any agent runs.
    """
    return {
        "current_index": 0,
        "dataset_id": "nwokikeonyeka/maa-cambridge-south-eastern-nigeria",
        "active_agent": "",
        "completed_agents": [],
        "last_ui_update": 0.0,
        "draft_payload": {},
        "image_path": "",
        "critic_status": ""
    }

class ArchiveCreate(BaseModel):
    """
    Master Output Schema aligned with Igbo Archives REST API POST /api/v1/archives/
    Descriptions here act as secondary constraints for the LLM.
    """
    title: str = Field(description="Formal archival title. MUST NOT contain AI-isms or em-dashes.")
    archive_type: str = Field(description="Strictly output 'image' here.")
    original_author: Optional[str] = Field(description="Exact case-sensitive 'name' from the LIVE TAXONOMY DATA. If not in DB, use source name. Do not invent authors.")
    description: Optional[str] = Field(description="Meticulous cultural report. NO em-dashes, NO generic AI words. Facts strictly from source.")
    caption: Optional[str] = Field(description="Concise caption for the photograph.")
    alt_text: Optional[str] = Field(description="Accessibility text (e.g., 'Young Igbo Woman Painted with Uli').")
    circa_date: Optional[str] = Field(description="Approximate date (e.g., '1932-1938', '1930s'). Return null if entirely unknown.")
    location: Optional[str] = Field(description="Specific location info. Return null if entirely unknown.")
    copyright_holder: Optional[str] = Field(default="MAA Cambridge", description="The copyright holder. Defaults to MAA Cambridge.")
    original_url: Optional[str] = Field(description="Source URL from the Hugging Face dataset.")
    original_identity_number: Optional[str] = Field(description="Museum or ID number (idno).")
    category_id: Optional[int] = Field(description="Numeric ID strictly from the taxonomy tool.")