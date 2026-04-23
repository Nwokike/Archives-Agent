import os
import httpx
import json
import asyncio
import mimetypes
from dotenv import load_dotenv
from typing import Dict, Any, Optional

load_dotenv()

MCP_URL = "https://igboarchives.com.ng/api/mcp/"

async def call_mcp_tool(server_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Robust JSON-RPC client for the Igbo Archives MCP server.
    Includes built-in asynchronous backoff to prevent API rate limiting.
    """
    api_token = os.getenv("IGBO_ARCHIVES_TOKEN")
    if not api_token:
        return {"error": "IGBO_ARCHIVES_TOKEN not found in environment."}

    await asyncio.sleep(1.5)

    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {}
        }
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            if tool_name == "create_archives" and "body" in (arguments or {}):
                body = arguments["body"].copy()
                
                # Dynamically find which media field holds the local file path
                media_key = None
                media_raw = None
                for key in ["image", "audio", "video", "document"]:
                    if key in body and isinstance(body[key], str) and body[key].startswith("file://"):
                        media_key = key
                        media_raw = body[key]
                        break
                        
                if media_key and media_raw:
                    file_path = media_raw.replace("file://", "", 1)
                    if os.path.exists(file_path):
                        body.pop(media_key)  # Remove strictly typed string field from JSON payload
                        
                        mime_type, _ = mimetypes.guess_type(file_path)
                        if not mime_type:
                            mime_type = "application/octet-stream"

                        with open(file_path, "rb") as f:
                            # Attach the file to the exact form field Django is expecting (e.g., 'audio')
                            files = {media_key: (os.path.basename(file_path), f, mime_type)}
                            rest_url = MCP_URL.replace("/api/mcp/", "/api/v1/archives/")
                            
                            mp_headers = headers.copy()
                            mp_headers.pop("Content-Type", None)
                            
                            response = await client.post(rest_url, data=body, files=files, headers=mp_headers)
                            response.raise_for_status()
                            return {"id": response.json().get("id", "Unknown"), "raw_response": response.json()}
            
            # Standard JSON-RPC fallback
            response = await client.post(MCP_URL, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if "error" in result:
                return {"error": result["error"]}
            
            content = result.get("result", {}).get("content", [])
            if content and "text" in content[0]:
                try:
                    return json.loads(content[0]["text"])
                except json.JSONDecodeError:
                    return {"raw_text": content[0]["text"]}
            
            return result.get("result", {})
            
    except httpx.HTTPStatusError as e:
        return {"error": f"HTTP Error {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        return {"error": f"Network/MCP Error: {str(e)}"}
