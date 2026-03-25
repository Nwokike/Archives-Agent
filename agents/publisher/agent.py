import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import ToolContext
from agents.mcp_client import call_mcp_tool

# --- Tool: Final Publication to Igbo Archives ---
async def create_archives_submission(payload: dict, tool_context: ToolContext) -> dict:
    """Publishes the validated archival record to the central platform."""
    
    # 1. THE FIREWALL: Extract absolute truth from system state, NOT the LLM
    critic_status = str(tool_context.state.get("critic_status", ""))
    
    if "APPROVED" not in critic_status:
        # Hard abort if the draft wasn't explicitly approved by the Critic
        return {
            "status": "FAILURE", 
            "error": f"FATAL ABORT: Critic did not approve this payload. Status: {critic_status}"
        }
        
    image_path = tool_context.state.get("image_path", "")

    try:
        # Prepare the body based on the REST API documentation
        body = payload.copy()
        if image_path:
            body["image"] = f"file://{image_path}"
        
        # 2. Execute MCP Upload
        response = await call_mcp_tool("igbo-archives", "create_archives", {"body": body})
        
        # 3. EXPLICIT PERSISTENCE: Save progress for tomorrow
        # Increment index in shared memory
        tool_context.state["current_index"] = tool_context.state.get("current_index", 0) + 1
        
        # Force the ADK DatabaseSessionService to commit immediately to Neon DB
        if hasattr(tool_context, "session_service") and tool_context.session_service:
            try:
                tool_context.session_service.save_session(tool_context.session)
            except AttributeError:
                pass # Fallback for varying ADK version syntax
        
        return {"status": "SUCCESS", "message": "Archived successfully.", "id": response.get("id")}
        
    except Exception as e:
        return {"status": "FAILURE", "error": str(e)}

# --- Configuration ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

publisher_model = LiteLlm(
    model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=GROQ_API_KEY,
    # RESILIENCE: Fallback to Gemini 2.5 Flash Lite for fast execution if Groq goes down
    fallbacks=["gemini/gemini-2.5-flash-lite"]
)

# --- Agent E: The Publisher ---
publisher = Agent(
    name="publisher",
    model=publisher_model,
    description="Agent E: The final record publisher and database committer.",
    tools=[create_archives_submission],
    instruction="""
ROLE:
You are the Final Executioner for the Igbo Archives.

GOAL:
Take the validated JSON payload from the Synthesis Loop and push it to the live database using your tool.

AVAILABLE DATA:
- The `archive` JSON payload drafted by the Synthesis Writer.

STRICT RULES:
1. ZERO MODIFICATION: You must pass the exact, unmodified JSON payload into your tool. Do not change a single character of the Writer's draft.
2. SINGLE ACTION: Your only job is to trigger the `create_archives_submission` tool.

TOOL MANDATE:
Trigger the `create_archives_submission` tool and pass the JSON payload. Do not attempt to pass an image_path or critic_status—the tool securely extracts those directly from the system state firewall.
"""
)