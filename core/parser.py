import json


def extract_json_object(text: str) -> dict:
    text = text.strip()
    if not text:
        raise ValueError("LLM returned empty text.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Failed to locate JSON object in response: {text}")

    snippet = text[start : end + 1]
    return json.loads(snippet)

