from google.adk.agents import Agent
from agents.mcp_client import call_mcp_tool

# Tool: Final Publication to Igbo Archives
async def create_archives_submission(payload: dict, image_path: str) -> dict:
    """Publishes the validated archival record to the central platform."""
    try:
        # Prepare the body based on the REST API documentation
        # Ensure image is passed as a file URL for the MCP tool to resolve
        body = payload.copy()
        
        # Mapping from schema to API fields if necessary
        # The schema ArchiveCreate already matches the API Body fields:
        # title, archive_type, description, caption, alt_text, circa_date, 
        # location, copyright_holder, original_url, original_identity_number, category_id
        
        if image_path:
            body["image"] = f"file://{image_path}"
            
        # Call the MCP tool 'create_archives' which expects {"body": {...}}
        response = await call_mcp_tool("igbo-archives", "create_archives", {"body": body})
        return {"status": "SUCCESS", "message": "Archived successfully.", "id": response.get("id")}
    except Exception as e:
        return {"status": "FAILURE", "error": str(e)}

# Publisher Agent
publisher = Agent(
    name="publisher",
    model="gemini-2.5-flash-lite",
    description="Agent E: The final record publisher.",
    instruction="""
    3. COMMIT: If and ONLY IF the state indicates the draft has been 'APPROVED' by the Historical Validator, call the `create_archives_submission` tool. 
    4. ABORT: If the 'APPROVED' status is missing or the Validator has feedback, do NOT call the tool and return a failure message.
    
    If failed, report the error exactly.
    """
)
