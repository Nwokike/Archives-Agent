import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

from typing import Dict, Any, Optional

MCP_URL = "https://archives.kiri.ng/api/mcp/"
API_TOKEN = os.getenv("IGBO_ARCHIVES_TOKEN")

async def call_mcp_tool(server_name: str, tool_name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Robust JSON-RPC client for the Igbo Archives MCP server.
    Follows 'Master Architecture Blueprint' and current platform docs.
    """
    if not API_TOKEN:
        return {"error": "IGBO_ARCHIVES_TOKEN not found in environment."}

    headers = {
        "Authorization": f"Token {API_TOKEN}",
        "Content-Type": "application/json"
    }

    # Standard JSON-RPC payload for MCP via HTTP
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": f"tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments or {}
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(MCP_URL, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if "error" in result:
                return {"error": result["error"]}
            
            # MCP response format: result -> content -> [text/json]
            content = result.get("result", {}).get("content", [])
            if content and "text" in content[0]:
                try:
                    return json.loads(content[0]["text"])
                except:
                    return {"raw_text": content[0]["text"]}
            
            return result.get("result", {})
            
    except Exception as e:
        return {"error": str(e)}
    
    return {"error": "Unknown terminal error in MCP client."}
