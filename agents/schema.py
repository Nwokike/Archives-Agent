import json
from google_adk import SessionState

class PipelineState(SessionState):
    """Shared Persistent Memory for the Igbo Archives Ingestion Pipeline."""
    repo_id: str = "nwokikeonyeka/maa-cambridge-south-eastern-nigeria"
    current_index: int = 0
    last_processed_id: str = ""
    status: str = "idle"
    loop_count: int = 0
    hf_metadata: dict = {}
    image_path: str = ""
    vision_report: str = ""
    taxonomies: dict = {"authors": [], "categories": []}
    draft_payload: dict = {}
    corrections: str = ""
    last_success_timestamp: str = ""

    def get_context_summary(self):
        return f"Currently at index {self.current_index}. Last success: {self.last_success_timestamp}"
