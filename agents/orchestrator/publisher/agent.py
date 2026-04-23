import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import ToolContext
from ..mcp_client import call_mcp_tool
from ..schema import ArchiveCreate  

async def create_archives_submission(payload: ArchiveCreate, tool_context: ToolContext) -> dict:
    """Publishes the validated archival record to the central platform."""
    
    # 1. PRE-FLIGHT CHECK
    image_path = tool_context.state.get("image_path", "")
    if not image_path or not os.path.exists(image_path):
        return {
            "status": "FAILURE",
            "error": "FATAL ABORT: Valid image path not found. Pipeline failed in an earlier stage."
        }

    # 2. THE FIREWALL
    critic_status = str(tool_context.state.get("critic_status", ""))
    
    if "APPROVED" not in critic_status:
        return {
            "status": "FAILURE", 
            "error": f"FATAL ABORT: Critic did not approve this payload. Status: {critic_status}"
        }

    try:
        body = payload.model_dump()
        
        # We know image_path is valid now due to the pre-flight check
        # Our updated mcp_client.py intercepts the file:// protocol and uses multipart upload
        body["image"] = f"file://{image_path}"
        
        # 3. Execute MCP Upload
        response = await call_mcp_tool("igbo-archives", "create_archives", {"body": body})
        
        # --- Catch Silent MCP Errors ---
        response_str = str(response)
        if "Error executing tool" in response_str or "ErrorDetail" in response_str or not response.get("id"):
            return {
                "status": "FAILURE", 
                "error": f"MCP API Error: The remote server rejected the payload. Details: {response.get('raw_response', {}).get('raw_text', response_str)}"
            }
        
        # 4. EXPLICIT PERSISTENCE
        tool_context.state["current_index"] = tool_context.state.get("current_index", 0) + 1
        
        # Force the ADK DatabaseSessionService to commit immediately
        if hasattr(tool_context, "session_service") and tool_context.session_service:
            try:
                tool_context.session_service.save_session(tool_context.session)
            except AttributeError:
                pass 
        
        return {"status": "SUCCESS", "message": "Archived successfully.", "id": response.get("id")}
        
    except Exception as e:
        return {"status": "FAILURE", "error": str(e)}

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

publisher_model = LiteLlm(
    model="gemini/gemini-3.1-flash-lite-preview",
    api_key=GEMINI_API_KEY,
    fallbacks=["gemini/gemma-4-26b-a4b-it", "gemini/gemma-4-31b-it"]
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
1. ZERO MODIFICATION: You must pass the exact data from the Writer into your tool. 
2. EXACTLY ONE ACTION: You are strictly forbidden from calling the `create_archives_submission` tool more than once per execution.
3. HANDLING SUCCESS: If the tool returns "SUCCESS", immediately output a brief text confirmation of the success and STOP. Do not process the next index.
4. HANDLING FAILURE: If the tool returns "FAILURE" (e.g., Critic did not approve), DO NOT attempt to retry or fix the payload. Immediately output the exact error message as text and STOP.

TOOL MANDATE:
Trigger the `create_archives_submission` tool. Map the Writer's draft perfectly to the tool's parameters. Do not attempt to pass an image_path or critic_status. Once the tool returns a response, output your final text and cease operations.
"""
)
