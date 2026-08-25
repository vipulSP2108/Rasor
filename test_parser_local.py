from src.agent.parser import parse_user_intent
from src.agent.brain import AgentBrain

try:
    parsed = parse_user_intent("give me 3 black tees in large size")
    print("Parsed raw:", parsed.model_dump())

    brain = AgentBrain()
    canonical, src = brain.normalize_intent("give me 3 black tees in large size")
    print("\nCanonical:", canonical.model_dump())
    print("\nSUCCESS!")
except Exception as e:
    import traceback
    print("ERROR:")
    traceback.print_exc()
