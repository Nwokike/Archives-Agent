from google_adk import SupervisorAgent, WorkflowAgent, Node
from ..schema import PipelineState
from ..fetcher.agent import FetcherAgent
from ..vision.agent import VisionAgent
from ..synthesis.agent import SynthesisLoop
from ..publisher.agent import PublisherAgent

class ArchivePipeline(WorkflowAgent):
    nodes = [
        Node(FetcherAgent(), id="fetcher"),
        Node(VisionAgent(), id="vision"),
        Node(SynthesisLoop(), id="synthesis"),
        Node(PublisherAgent(), id="publisher")
    ]

class Orchestrator(SupervisorAgent):
    model = "gemini-3.1-flash-lite"
    tools = [ArchivePipeline().as_tool("execute_archive_pipeline")]
    system_prompt = "You are the Igbo Archives Orchestrator. Manage the archiving pipeline."
