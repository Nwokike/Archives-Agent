from pydantic import BaseModel
from typing import Dict, Any, Optional

class PipelineState(BaseModel):
    """
    Master Ingestion System State.
    Aligned with 'Master Architecture Blueprint' Table Schema.
    """
    dataset_id: str = "nwokikeonyeka/maa-cambridge-south-eastern-nigeria" # PK in Neon
    current_index: int = 0
    last_processed_id: str = ""
    status: str = "idle"
    last_success: str = "" # Timestamp of last successful archive
    
    # Internal Pipeline Memory
    hf_metadata: Dict[str, Any] = {}
    image_path: str = ""
    vision_report: str = ""
    taxonomies: Dict[str, Any] = {"authors": [], "categories": []}
    draft_payload: Dict[str, Any] = {}
    loop_count: int = 0
    
    def get_context_summary(self) -> str:
        return f"Dataset: {self.dataset_id} | Index: {self.current_index} | Status: {self.status}"

def get_initial_state() -> Dict[str, Any]:
    """Returns the starting state as a dictionary for ADK SessionService."""
    return PipelineState().model_dump()
