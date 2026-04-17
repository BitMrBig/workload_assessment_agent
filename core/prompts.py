from pathlib import Path


PROMPT_DIR = Path(__file__).resolve().parent.parent / "agents"


def load_prompt(agent_name: str) -> str:
    prompt_path = PROMPT_DIR / f"{agent_name}.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")

