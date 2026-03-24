from google.adk.agents import Agent, LoopAgent
from pydantic import BaseModel, Field
from typing import Optional

# Aligned with Igbo Archives REST API POST /api/v1/archives/
class ArchiveCreate(BaseModel):
    title: str = Field(description="Formal archival title. MUST NOT contain AI-isms or em-dashes.")
    archive_type: str = "image"
    description: Optional[str] = Field(description="Meticulous cultural report. NO em-dashes. No generic AI words.")
    caption: Optional[str] = Field(description="Concise caption.")
    alt_text: Optional[str] = Field(description="Accessibility text.")
    circa_date: Optional[str] = Field(description="Approximate date (e.g., '1932-1938').")
    location: Optional[str] = Field(description="Specific location info.")
    copyright_holder: Optional[str] = Field(description="Copyright owner.")
    original_url: Optional[str] = Field(description="Source URL from dataset.")
    original_identity_number: Optional[str] = Field(description="Museum or ID number (idno).")
    category_id: Optional[int] = Field(description="Numeric ID from taxonomy tool.")

# Agent C: The Writer
writer = Agent(
    name="synthesis_writer",
    model="gemini-3-flash-preview",
    description="Agent C: The metadata synthesizer. Strict Fact-to-Field mapping.",
    instruction="""
    Synthesize the input into the ArchiveCreate schema.
    
    STRICT CONSTRAINTS:
    1. NO EM-DASHES (—). Use commas, colons, or parentheses if needed.
    2. NO AI SPEAK: Avoid words like 'research', 'pioneer', 'delve', 'tapestry', 'explore', 'comprehensive', 'vibrant', 'tapestry'. 
    3. NO HALLUCINATION: If a field is not found in source metadata or vision report, leave it as 'null'.
    4. NO ASSUMPTIONS: Do not assume author if not listed as photographer.
    5. NEUTRAL TONE: Use clinical, archival language.
    """,
    output_schema=ArchiveCreate,
    output_key="archive"
)

# Agent D: The Critic
critic = Agent(
    name="historical_validator",
    model="gemini-2.5-flash-lite",
    description="Agent D: The evaluator. Enforcer of constraints.",
    instruction="""
    Verify the Writer's draft for compliance.
    REJECT if:
    - Contains em-dashes (—).
    - Contains AI-isms ('research', 'tapestry', 'delve', etc.).
    - Contains data not present in source metadata (Hallucination).
    - Contains generic/unnecessary filler text.
    
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
