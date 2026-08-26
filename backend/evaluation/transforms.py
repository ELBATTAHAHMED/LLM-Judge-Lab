"""Deterministic, non-provider controls for RQ4 and RQ5."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return " ".join(text.split()).casefold()


def make_verbosity_variant(original: str) -> str:
    """Use only an exact duplicate: redundant length with no added propositions."""
    if not original.strip():
        raise ValueError("Cannot create a verbosity control from empty text")
    return original + "\n\n" + original


def make_format_variant(original: str) -> str:
    """Add only leading list syntax; no headings, labels, or rewritten wording."""
    if not original.strip():
        raise ValueError("Cannot create a format control from empty text")
    return "\n".join(("- " + line if line.strip() else line) for line in original.splitlines())


def strip_formatting(text: str) -> str:
    return "\n".join(re.sub(r"^\s*(?:[-*+] |\d+[.)] |#{1,6}\s+)", "", line) for line in text.splitlines())


@dataclass(frozen=True)
class VariantValidation:
    variant_type: str
    source_checksum: str
    variant_checksum: str
    source_word_count: int
    variant_word_count: int
    valid: bool
    status: str
    details: str


def validate_verbosity_variant(source_answer_id: int, original: str, variant: str) -> VariantValidation:
    expected = make_verbosity_variant(original) if original.strip() else None
    valid = bool(source_answer_id > 0 and expected is not None and variant == expected and len(variant.split()) > len(original.split()))
    return VariantValidation("VERBOSITY_REDUNDANCY", checksum(original), checksum(variant), len(original.split()), len(variant.split()), valid, "VALID" if valid else "REJECTED", "Exact duplicate only; any added or altered text is rejected.")


def validate_format_variant(source_answer_id: int, original: str, variant: str) -> VariantValidation:
    equivalent = normalize_text(original) == normalize_text(strip_formatting(variant))
    valid = bool(source_answer_id > 0 and original.strip() and variant.strip() and equivalent)
    return VariantValidation("FORMAT_ONLY", checksum(original), checksum(variant), len(original.split()), len(variant.split()), valid, "VALID" if valid else "REJECTED", "Normalized original must exactly equal syntax-stripped variant.")
