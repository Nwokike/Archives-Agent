import os
from google.genai import types
from google.adk.agents import Agent, LoopAgent, BaseAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.events import Event, EventActions
from ..schema import ArchiveCreate

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Models ---
writer_model = LiteLlm(
    model="gemini/gemma-4-31b-it",
    api_key=GEMINI_API_KEY,
    fallbacks=["gemini/gemma-4-26b-a4b-it"]
)

critic_model = LiteLlm(
    model="gemini/gemma-4-26b-a4b-it",
    api_key=GEMINI_API_KEY,
    fallbacks=["gemini/gemma-4-31b-it"]
)

writer = Agent(
    name="synthesis_writer",
    model=writer_model,
    description="Agent C: The metadata synthesizer. Strict Fact-to-Field mapping.",
    output_schema=ArchiveCreate,
    output_key="archive",
    instruction="""
ROLE:
You are an Elite Cultural Heritage Metadata Synthesizer.

GOAL:
Merge massive raw historical metadata, the visual analyst's report, and live taxonomy into a flawless JSON archival record.

AVAILABLE DATA:
- `raw_metadata` (Unedited historical context from the data fetcher)
- The visual report (from the vision analyst)
- `research_context` (UNVERIFIED internet search results. Use this ONLY as supplementary context or an 'advantage' to help you better understand the raw metadata. It is NOT a source of truth.)
- LIVE TAXONOMY DATA (Authors and Categories from the database)

STRICT RULES:
1. NO EM-DASHES: You are strictly forbidden from using em-dashes (—). Use commas, colons, or parentheses.
2. NO AI SPEAK: Completely ban words like 'pioneer', 'delve', 'tapestry', 'explore', 'comprehensive', 'vibrant', 'intricate', 'dives'.
3. HONEST NULL: The primary sources of truth are the `raw_metadata` and the vision report. If a primary field (like the core location or date) is missing from them, leave it as proper JSON `null`. Do not invent new primary facts based solely on the unverified `research_context`.
4. AUTHOR RESOLUTION: Check the LIVE TAXONOMY DATA. If the author exists in our database, you MUST output their exact case-sensitive 'name' from the taxonomy into the `original_author` field. If they do not exist, format the name based on the source metadata.
5. TONE: Use clinical, objective, archival language.

GOLD STANDARD EXAMPLES:
Study these examples of perfect archival submissions:

Title: Young Igbo Girl Painted with Uli
Description: This black-and-white photograph from the 1940s by Sylvia Leith-Ross shows a young Igbo girl adorned with traditional Uli body art patterns. She wears a headpiece with feathers and decorative elements, with her back turned to emphasize the designs. Blurred figures in the background suggest a public event. The image highlights the cultural significance of Uli in Igbo identity and aesthetics, as documented in Leith-Ross's book African Conversation Piece (1944).
Caption: A young Igbo girl painted with Uli. From Sylvia Leith-Ross, African Conversation Piece, London/New York: Hutchinson, 1944.
Alt Text: Young Igbo Woman Painted with Uli on her back.
Circa Date: c1930
Location: Asaba (present-day Delta State, Nigeria). 
Original URL: https://www.britishmuseum.org/collection/object/EA_Af-B58-36
Original Identity Number: Af-B58-36

Additional style references:
- Title should be formal and specific.
- Description should stay factual, neutral, and source-bound.
- Caption should be concise and publication-like.
- Alt text should be short and accessible.
- Use the bracketed format for modern place names, like Asaba (present-day Delta State, Nigeria). If the present location is unknown, leave out the brackets and write only the location name. If the location is unknown, leave the location field empty. Also for circa date you can write it like these depending on what is provided 1932-1938 or 1930s or c1930.
"""
)

# --- Agent D: The Critic ---
critic = Agent(
    name="historical_validator",
    model=critic_model,
    description="Agent D: The evaluator. Enforcer of constraints.",
    output_key="critic_status",
    instruction="""
ROLE:
You are an Elite Archival Quality Assurance Validator.

GOAL:
Review the Writer's drafted JSON payload against strict formatting and historical authenticity rules.

AVAILABLE DATA:
- The JSON draft from the Synthesis Writer.
- The original source metadata, visual report, taxonomy data, and `research_context`.

STRICT RULES (REJECT THE DRAFT IF ANY OF THESE FAIL):
1. REJECT if the draft contains em-dashes (—).
2. REJECT if the draft contains AI-isms ('tapestry', 'vibrant', 'intricate', 'delve', etc.).
3. REJECT if the draft hallucinates completely made-up facts NOT found in the raw metadata, visual report, OR the `research_context`.
   - DO NOT be pedantic about primary vs. secondary context. It is FULLY ACCEPTABLE and encouraged for the Writer to seamlessly integrate findings from the `research_context` into the formal description without explicitly tagging them as secondary. If the facts are supported by the research, ACCEPT the draft.
4. REJECT if the author exists in the LIVE TAXONOMY DATA but the Writer failed to use the exact case-sensitive spelling.

OUTPUT MANDATE:
- If the draft is flawless, you MUST reply with exactly one word: APPROVED.
- If it fails, list the exact REJECTION reasons clearly so the Writer can fix them in the next iteration.
"""
)

# --- The Deterministic Loop Breaker ---
class CriticEscalationChecker(BaseAgent):
    """A deterministic agent that checks the critic's status and terminates the loop."""
    name: str = "escalation_checker"
    
    async def _run_async_impl(self, context):
        # Read the status from the shared session state
        status = context.session.state.get("critic_status", "")
        
        if "APPROVED" in status.upper():
            # Yielding an event with escalate=True acts as the loop breaker
            yield Event(
                author=self.name, 
                actions=EventActions(escalate=True)
            )
        else:
            # Otherwise, yield a properly formatted Content object and let the LoopAgent restart
            yield Event(
                author=self.name,
                content=types.Content(
                    role="system",
                    # FIX APPLIED HERE: Added 'text=' keyword argument
                    parts=[types.Part.from_text(text="Draft not approved. Continuing refinement loop.")]
                )
            )

escalation_checker = CriticEscalationChecker()

# --- The Master Loop Agent ---
synthesis_loop = LoopAgent(
    name="synthesis_loop",
    max_iterations=3,
    sub_agents=[writer, critic, escalation_checker],
    description="Loop Agent: Ensures cultural authenticity and metadata precision."
)