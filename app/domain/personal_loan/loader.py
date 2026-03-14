import json
from functools import lru_cache
from pathlib import Path

from app.domain.models import (
    IntentDefinition,
    ProductSpec,
    ScriptDefinition,
    SlotDefinition,
)

BASE_DIR = Path(__file__).resolve().parent


def _read_json(filename: str):
    file_path = BASE_DIR / filename
    with file_path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache
def load_intents() -> list[IntentDefinition]:
    data = _read_json("intents.json")
    return [IntentDefinition(**item) for item in data]


@lru_cache
def load_slots() -> list[SlotDefinition]:
    data = _read_json("slots.json")
    return [SlotDefinition(**item) for item in data]


@lru_cache
def load_script() -> ScriptDefinition:
    data = _read_json("script.json")
    return ScriptDefinition(**data)


@lru_cache
def load_flow_markdown() -> str:
    return (BASE_DIR / "flow.md").read_text(encoding="utf-8")


@lru_cache
def load_product_spec() -> ProductSpec:
    return ProductSpec(
        product="personal_loan",
        intents=load_intents(),
        slots=load_slots(),
        script=load_script(),
        flow_markdown=load_flow_markdown(),
    )