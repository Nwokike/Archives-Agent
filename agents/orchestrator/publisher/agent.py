import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import ToolContext
from ..mcp_client import call_mcp_tool
from ..schema import ArchiveCreate  

async def create_archives_submission(payload: dict | list, tool_context: ToolContext) -> dict:
    """Publishes the validated archival record to the central platform."""
    
    # 0. THE LIST UNWRAPPER (Bulletproof Pydantic Fix)
    if isinstance(payload, list):
        if len(payload) > 0:
            payload = payload[0]  # Unwrap the array and extract the JSON object
        else:
            return {
                "status": "FAILURE",
                "error": "FATAL ABORT: Received an empty list instead of a valid payload."
            }
            
    # Manually validate against your schema now that we are guaranteed to have a dict
    try:
        validated_payload = ArchiveCreate(**payload)
    except Exception as e:
        return {
            "status": "FAILURE",
            "error": f"FATAL ABORT: Schema validation failed. {str(e)}"
        }

    # 1. PRE-FLIGHT MEDIA CHECK (Universal Support for Audio & Images)
    # Checks for the new universal media_path first, falls back to legacy image_path
    file_path = tool_context.state.get("media_path", tool_context.state.get("image_path", ""))
    
    if not file_path or not os.path.exists(file_path):
        return {
            "status": "FAILURE",
            "error": "FATAL ABORT: Valid media file path not found. Pipeline failed in an earlier stage."
        }

    # 2. THE FIREWALL
    critic_status = str(tool_context.state.get("critic_status", ""))
    
    if "APPROVED" not in critic_status:
        return {
            "status": "FAILURE", 
            "error": f"FATAL ABORT: Critic did not approve this payload. Status: {critic_status}"
        }

    try:
        body = validated_payload.model_dump()
        
        # 3. Execute MCP Upload
        # We attach the universal file path (audio or image) to the API payload
        body["image"] = f"file://{file_path}"
        
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
    model="gemini/gemma-4-26b-a4b-it",
    api_key=GEMINI_API_KEY,
    fallbacks=["gemini/gemma-4-31b-it"]
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
1. ZERO MODIFICATION: You must pass the exact data from the Writer into your tool as a single JSON object. DO NOT wrap it in a list [].
2. EXACTLY ONE ACTION: You are strictly forbidden from calling the `create_archives_submission` tool more than once per execution.
3. HANDLING SUCCESS: If the tool returns "SUCCESS", immediately output a brief text confirmation of the success and STOP. Do not process the next index.
4. HANDLING FAILURE: If the tool returns "FAILURE" (e.g., Critic did not approve), DO NOT attempt to retry or fix the payload. Immediately output the exact error message as text and STOP.

TOOL MANDATE:
Trigger the `create_archives_submission` tool. Map the Writer's draft perfectly to the tool's `payload` parameter. Do not attempt to pass media paths or critic status. Once the tool returns a response, output your final text and cease operations.
"""
)