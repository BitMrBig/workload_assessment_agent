import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class SessionStore:
    def __init__(self, base_dir: Path, config_path: Path):
        self.base_dir = base_dir
        self.config_path = config_path

    def create_session_dir(self, session_name: Optional[str] = None) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prefix = f"{session_name}_" if session_name else ""
        session_dir = self.base_dir / f"{prefix}{timestamp}"
        session_dir.mkdir(parents=True, exist_ok=False)
        self.write_text(session_dir / "config_path.txt", str(self.config_path.resolve()))
        return session_dir

    @staticmethod
    def write_json(path: Path, data: dict) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def write_text(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
