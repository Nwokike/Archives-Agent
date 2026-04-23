import os
import base64
import io
import PIL.Image
import litellm
import asyncio
from google.adk.agents import Context

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

def _encode_and_compress_image(image_path: str, max_size=(1024, 1024)) -> str:
    """
    Resizes the image to fit within Gemini's payload limits and converts it to base64.
    """
    with PIL.Image.open(image_path) as img:
        # Convert to RGB to avoid issues with PNG transparency or weird color spaces
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        # Downscale the image if it's too large (maintains aspect ratio)
        img.thumbnail(max_size)
        
        # Save to an in-memory buffer as a compressed JPEG
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG", quality=85)
        
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

async def execute_vision_analysis(ctx: Context) -> str:
    """
    Custom tool for the Orchestrator. 
    Compresses the image and includes a retry loop to bypass Gemini 500 errors.
    """
    image_path = ctx.state.get("image_path")
    
    if not image_path or not os.path.exists(image_path):
        error_msg = f"FATAL: Valid image not found at path: {image_path}"
        ctx.state["vision_report_error"] = error_msg
        return error_msg
        
    try:
        # 1. Compress and encode the image (Prevents size-based 500 errors)
        base64_image = _encode_and_compress_image(image_path)
        
        # 2. Add a simple retry loop for transient Gemini server hiccups
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await litellm.acompletion(
                    model="gemini/gemini-3.1-flash-lite-preview",
                    fallbacks=["gemini/gemma-4-31b-it", "gemini/gemma-4-26b-a4b-it"], 
                    api_key=GEMINI_API_KEY,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": (
                                        "ROLE: You are an Elite Cultural Heritage Visual Analyst.\n"
                                        "GOAL: Meticulously examine the provided image and extract a purely visual, unbiased cultural report.\n"
                                        "STRICT RULES:\n"
                                        "1. NO HALLUCINATION: DO NOT invent historical context, names, locations, or events.\n"
                                        "2. TONE: Output your analysis as a highly detailed, clinical, and objective observational report."
                                    )
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{base64_image}"
                                    }
                                }
                            ]
                        }
                    ]
                )
                
                # Extract the text response
                result_text = response.choices[0].message.content
                
                # HOIST SUCCESS TO MAIN STATE
                ctx.state["vision_report"] = result_text
                
                # If we had a previous error in state from a failed attempt, clear it
                if "vision_report_error" in ctx.state:
                    del ctx.state["vision_report_error"]
                    
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
        error_msg = f"Vision API/Model Error after retries: {str(e)}"
        ctx.state["vision_report_error"] = error_msg
        return error_msg