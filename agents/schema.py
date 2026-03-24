import json
from google_adk import SessionState

class PipelineState(SessionState):
    """
    Shared Persistent Memory for the Igbo Archives Ingestion Pipeline.
    Linked to Neon DB via DatabaseSessionService.
    """
    repo_id: str = "nwokikeonyeka/maa-cambridge-south-eastern-nigeria"
    current_index: int = 0
    last_processed_id: str = ""
    
    # State flags
    status: str = "idle"
    loop_count: int = 0
    
    # Payload & Data (Ephemeral per-run)
    hf_metadata: dict = {}
    image_path: str = ""
    vision_report: str = ""
    taxonomies: dict = {"authors": [], "categories": []}
    draft_payload: dict = {}
    corrections: str = ""
    last_success_timestamp: str = ""

    def get_context_summary(self):
        """Used by Orchestrator to understand current progress."""
        return f"Currently at index {self.current_index}. Last success: {self.last_success_timestamp}"
