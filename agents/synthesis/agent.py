from google.adk.agents import Agent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
from pydantic import BaseModel, Field
from typing import Optional
import os

class ArchiveCreate(BaseModel):
    title: str = Field(description="Formal archival title. MUST NOT contain AI-isms or em-dashes (e.g., 'Igbo Elder from Awka on Oche Mpata').")
    archive_type: str = "image"
    author_name: Optional[str] = Field(description="Name of the author. You MUST use the exact 'name' field from the taxonomist output (case-sensitive), NEVER the 'slug' or 'description'. If the author does not exist in our db, write their name based on the source information, never making anything up (e.g., 'Northcote Thomas').")
    description: Optional[str] = Field(description="Meticulous cultural report. NO em-dashes, NO generic AI words, don't make up anything you are not sure of so get all your facts from the provided content. (e.g., 'This black-and-white photograph from the 1940s by Sylvia Leith-Ross shows a young Igbo girl adorned with traditional Uli body art patterns. She wears a headpiece with feathers and decorative elements, with her back turned to emphasize the designs. Blurred figures in the background suggest a public event. The image highlights the cultural significance of Uli in Igbo identity and aesthetics, as documented in Leith-Ross's book African Conversation Piece (1944)').")
    caption: Optional[str] = Field(description="Concise caption (e.g., ' A young Igbo girl painted with Uli. From Sylvia Leith-Ross, African Conversation Piece, London/New York: Hutchinson, 1944.').")
    alt_text: Optional[str] = Field(description="Accessibility text (e.g., 'Young Igbo Woman Painted with Uli on her back').")
    circa_date: Optional[str] = Field(description="Approximate date (e.g., '1932-1938', 'c. 1935', '1930s').")
    location: Optional[str] = Field(description="Specific location info (e.g., 'Near Bende, Abia State, Nigeria').")
    copyright_holder: Optional[str] = Field(description="Copyright owner (e.g., 'MAA Cambridge').")
    original_url: Optional[str] = Field(description="Source URL from dataset (e.g., 'https://www.britishmuseum.org/collection/object/EA_Af-B58-36').")
    original_identity_number: Optional[str] = Field(description="Museum or ID number (idno) (e.g., 'Af-B58-36').")
    category_id: Optional[int] = Field(description="Numeric ID from taxonomy tool.")

# Agent C: The Writer
writer_model = LiteLlm(
    model="groq/llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY")
)

writer = Agent(
    name="synthesis_writer",
    model=writer_model,
    description="Agent C: The metadata synthesizer. Strict Fact-to-Field mapping.",
    instruction="""
    Synthesize the input into the ArchiveCreate schema.
    
    STRICT CONSTRAINTS:
    1. NO EM-DASHES (—). Use commas, colons, or parentheses if needed.
    2. NO AI SPEAK: Avoid words like 'research', 'pioneer', 'delve', 'tapestry', 'explore', 'comprehensive', 'vibrant', 'tapestry'. 
    3. NO HALLUCINATION: If a field is not found in source metadata or vision report, leave it as proper JSON `null`, NOT the string "null". You MUST include every field in the output schema.
    4. NO ASSUMPTIONS: Do not assume author if not listed as photographer.
    5. NEUTRAL TONE: Use clinical, archival language.
    6. AUTHOR RESOLUTION: Check the LIVE TAXONOMY DATA. If the Hugging Face author already exists in our taxonomy (even if formatted slightly differently, e.g., 'G.I. Jones' vs 'Jones, G.I.'), you MUST output their exact case-sensitive 'name' from the LIVE TAXONOMY DATA to prevent duplicates. If not in the database, use the Hugging Face name format.
    """,
    output_schema=ArchiveCreate,
    output_key="archive"
)

# Agent D: The Critic
critic_model = LiteLlm(
    model="groq/openai/gpt-oss-20b",
    api_key=os.getenv("GROQ_API_KEY")
)

critic = Agent(
    name="historical_validator",
    model=critic_model,
    description="Agent D: The evaluator. Enforcer of constraints.",
    instruction="""
    Verify the Writer's draft for compliance.
    REJECT if:
    - Contains em-dashes (—).
    - Contains AI-isms ('research', 'tapestry', 'vibrant', 'intricate', 'delve', etc.).
    - Contains data not present in source metadata or taxonomist (Hallucination).
    - Contains generic/unnecessary filler text.

    If the Author is already in our db from the taxonomist, make sure the author_name in the draft matches exactly what we got from the taxonomist (case sensitive), but if not already in our db only make sure it is from the provided content and not hallucinated.
    Reply 'APPROVED' if perfect. Otherwise, list REJECTION reasons clearly.
    """
)

# Synthesis Loop
synthesis_loop = LoopAgent(
    name="synthesis_loop",
    max_iterations=3,
    sub_agents=[writer, critic],
    description="Loop Agent: Ensures cultural authenticity and metadata precision."
)
