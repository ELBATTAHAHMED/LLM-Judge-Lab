"""Explicit evidence classes shared by API contracts and research views."""
from enum import Enum


class EvidenceClass(str, Enum):
    LEGACY_EXPLORATORY = "LEGACY_EXPLORATORY"
    CONTROLLED = "CONTROLLED"
    LIVE_SANDBOX = "LIVE_SANDBOX"
    PLANNED = "PLANNED"
    DRY_RUN_MOCK = "DRY_RUN_MOCK"
