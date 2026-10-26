"""Load simple local KEY=value settings without executing shell syntax or logging values."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"GROQ_API_KEY", "DATABASE_URL", "LOCAL_API_TOKEN", "LOCAL_DEVELOPMENT",
           "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"}


def load_local_env(path=None):
    path = Path(path) if path is not None else ROOT / ".env"
    if not path.is_file():
        return set()
    pending = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not separator or not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise ValueError(f"Invalid local environment entry on line {number}; use KEY=value.")
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f"Unclosed local environment value on line {number}.")
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].rstrip()
        if name in ALLOWED or name.startswith("MASTRR_"):
            pending[name] = value
    loaded = set()
    for name, value in pending.items():
        if name not in os.environ:
            os.environ[name] = value
            loaded.add(name)
    return loaded
