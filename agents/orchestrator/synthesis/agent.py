import os
from google.adk.agents import Agent, LoopAgent, BaseAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.events import Event, EventActions
from ..schema import ArchiveCreate

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

writer_model = LiteLlm(
    model="groq/moonshotai/kimi-k2-instruct-0905",
    api_key=GROQ_API_KEY,
    fallbacks=["groq/openai/gpt-oss-120b", "groq/meta-llama/llama-3.3-70b-versatile"]
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
- LIVE TAXONOMY DATA (Authors and Categories from the database)

STRICT RULES:
1. NO EM-DASHES: You are strictly forbidden from using em-dashes (—). Use commas, colons, or parentheses.
2. NO AI SPEAK: Completely ban words like 'research', 'pioneer', 'delve', 'tapestry', 'explore', 'comprehensive', 'vibrant', 'intricate'.
3. HONEST NULL: If a field (like location or date) is not found in the source metadata or vision report, leave it as proper JSON `null`. Do not invent facts.
4. AUTHOR RESOLUTION: Check the LIVE TAXONOMY DATA. If the author exists in our database, you MUST output their exact case-sensitive 'name' from the taxonomy. If they do not exist, format the name based on the source metadata.
5. TONE: Use clinical, objective, archival language.

GOLD STANDARD EXAMPLES:
Study these examples of perfect archival submissions. Match this exact tone, length, and formatting style:

Title: Igbo Elder from Awka on Oche Mpata
Description: This black-and-white photograph from the 1940s by Sylvia Leith-Ross shows a young Igbo girl adorned with traditional Uli body art patterns. She wears a headpiece with feathers and decorative elements, with her back turned to emphasize the designs. Blurred figures in the background suggest a public event. The image highlights the cultural significance of Uli in Igbo identity and aesthetics, as documented in Leith-Ross's book African Conversation Piece (1944).
Caption: A young Igbo girl painted with Uli. From Sylvia Leith-Ross, African Conversation Piece, London/New York: Hutchinson, 1944.
Alt Text: Young Igbo Woman Painted with Uli on her back.
Circa Date: 1932-1938 or 1930s or c1930
Location: Near Bende, Abia State, Nigeria
Original URL: https://www.britishmuseum.org/collection/object/EA_Af-B58-36
Original Identity Number: Af-B58-36

Additional style references:
- Title should be formal and specific.
- Description should stay factual, neutral, and source-bound.
- Caption should be concise and publication-like.
- Alt text should be short and accessible.
- If present, date and location should stay exact and unembellished.
"""
)

critic_model = LiteLlm(
    model="groq/llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
    fallbacks=["groq/openai/gpt-oss-120b", "groq/qwen/qwen3-32b"]
)

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
- The original source metadata and taxonomy data.

STRICT RULES (REJECT THE DRAFT IF ANY OF THESE FAIL):
1. REJECT if the draft contains em-dashes (—).
2. REJECT if the draft contains AI-isms ('tapestry', 'vibrant', 'intricate', 'delve', etc.).
3. REJECT if the draft contains facts/locations/dates not explicitly present in the massive raw metadata payload or visual report (Hallucination).
4. REJECT if the author exists in the LIVE TAXONOMY DATA but the Writer failed to use the exact case-sensitive spelling.
5. REJECT if the tone does not match the clinical, objective tone of the Gold Standard Examples provided to the Writer.

OUTPUT MANDATE:
- If the draft is 100% flawless, you MUST reply with exactly one word: APPROVED.
- If it fails, list the exact REJECTION reasons clearly so the Writer can fix them in the next iteration.
"""
)

class CriticEscalationChecker(BaseAgent):
    """A deterministic agent that checks the critic's status and terminates the loop."""
    name: str = "escalation_checker"
    
    async def _run_async_impl(self, context):
        # Read the status from the shared session state
        status = context.state.get("critic_status", "")
        
        if "APPROVED" in status.upper():
            # Yielding an event with escalate=True acts as the loop breaker
            yield Event(actions=EventActions(escalate=True))
        else:
            # Otherwise, do nothing and let the LoopAgent restart the cycle
            yield Event(content="Draft not approved. Continuing refinement loop.")

escalation_checker = CriticEscalationChecker()

synthesis_loop = LoopAgent(
    name="synthesis_loop",
    max_iterations=3,
    sub_agents=[writer, critic, escalation_checker],
    description="Loop Agent: Ensures cultural authenticity and metadata precision."
)