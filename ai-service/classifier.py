import json
import os
from pathlib import Path
from typing import Literal
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field


PROMPT_FILE = Path(__file__).parent / "prompts" / "v1" / "classify.txt"


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_type: Literal[
        "Transcript", "Degree certificate", "Language certificate", "Other", "Unknown"
    ]
    page: int | None = Field(ge=1)
    quote: str | None


def unknown() -> Classification:
    return Classification(document_type="Unknown", page=None, quote=None)


def classify_document(pages: list[dict]) -> Classification:
    text_by_page = {
        page["page"]: page["text"]
        for page in pages
        if isinstance(page.get("text"), str) and page["text"].strip()
    }
    if not text_by_page:
        return unknown()

    base_url = os.environ["OLLAMA_URL"].rstrip("/")
    payload = {
        "model": os.environ["CHAT_MODEL"],
        "stream": False,
        "format": Classification.model_json_schema(),
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": PROMPT_FILE.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps({"pages": pages})},
        ],
    }

    request = Request(
        f"{base_url}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urlopen(request, timeout=180) as response:
        reply = json.load(response)

    result = Classification.model_validate_json(reply["message"]["content"])

    if result.document_type == "Unknown":
        return unknown()

    source_text = text_by_page.get(result.page, "")
    if not result.quote or not result.quote.strip() or result.quote not in source_text:
        return unknown()

    return result