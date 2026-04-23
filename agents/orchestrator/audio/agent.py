import os
import base64
import mimetypes
import litellm
import asyncio
from google.adk.agents import Context

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def _encode_audio(audio_path: str) -> str:
    """
    Reads the audio file and converts it to base64.
    """
    with open(audio_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode('utf-8')

async def execute_audio_analysis(ctx: Context) -> str:
    """
    Custom tool for the Orchestrator. 
    Encodes the audio file and includes a retry loop to bypass possible 500 errors.
    """
    # The Traffic Cop saves both audio and images under the universal "media_path" key
    audio_path = ctx.state.get("media_path")
    
    if not audio_path or audio_path == "NONE" or not os.path.exists(audio_path):
        error_msg = f"FATAL: Valid audio file not found at path: {audio_path}"
        ctx.state["audio_report_error"] = error_msg
        return error_msg
        
    try:
        # 1. Encode the audio and determine its MIME type dynamically
        base64_audio = _encode_audio(audio_path)
        mime_type, _ = mimetypes.guess_type(audio_path)
        if not mime_type:
            mime_type = "audio/mpeg" # Safe fallback
            
        # 2. Add a simple retry loop to prevent possible server hiccups
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await litellm.acompletion(
                    model="gemini/gemini-3-flash-preview",
                    fallbacks=["gemini/gemini-3.1-flash-lite-preview"], 
                    api_key=GEMINI_API_KEY,
                    timeout=300,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": (
                                        "ROLE: You are an Elite Cultural Heritage Audio Analyst.\n"
                                        "GOAL: Meticulously listen to the provided audio and extract a purely auditory, unbiased cultural report.\n"
                                        "STRICT RULES:\n"
                                        "1. TRANSCRIBE & DESCRIBE: Document any spoken words, languages/dialects (if identifiable), musical instruments (like drums, gongs, flutes), vocal tones, rhythmic patterns, and ambient/background sounds.\n"
                                        "2. NO HALLUCINATION: DO NOT invent historical context, names, locations, or events not explicitly heard in the audio.\n"
                                        "3. TONE: Output your analysis as a highly detailed, clinical, and objective observational report."
                                    )
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{base64_audio}"
                                    }
                                }
                            ]
                        }
                    ]
                )
                
                # Extract the text response
                result_text = response.choices[0].message.content
                
                # HOIST SUCCESS TO MAIN STATE (Saved as media_report so Synthesis can find it easily)
                ctx.state["media_report"] = result_text
                
                # If we had a previous error in state from a failed attempt, clear it
                if "audio_report_error" in ctx.state:
                    del ctx.state["audio_report_error"]
                    
                return result_text
                
            except Exception as e:
                # If it's a 500 error, wait a second and try again
                if "500" in str(e) or "Internal Server Error" in str(e):
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2) # Backoff before retry
                        continue
                # If it's not a 500 error, or we ran out of retries, raise it
                raise e
                
    except Exception as e:
        # 3. HOIST FINAL ERRORS TO MAIN STATE
        error_msg = f"Audio API/Model Error after retries: {str(e)}"
        ctx.state["audio_report_error"] = error_msg
        return error_msg
