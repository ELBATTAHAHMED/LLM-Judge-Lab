"""Frozen pricing lookup used only for pre-request budget reservations."""
from __future__ import annotations
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

CONFIG = json.loads(Path(__file__).with_name("pricing_config.json").read_text(encoding="utf-8"))

@dataclass(frozen=True)
class TokenRate:
    input_per_token: Decimal
    output_per_token: Decimal

def price_for_model(judge_name: str) -> TokenRate:
    if CONFIG.get("status") != "VERIFIED_EXTERNAL_2026_08_18":
        raise PermissionError("pricing configuration is not verified/frozen")
    row = next((row for row in CONFIG["models"] if row["judge"] == judge_name), None)
    if row is None:
        raise PermissionError(f"no frozen price for {judge_name}")
    return TokenRate(Decimal(str(row["input_per_million_usd"])) / Decimal(1_000_000), Decimal(str(row["output_per_million_usd"])) / Decimal(1_000_000))
