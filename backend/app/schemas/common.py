"""Shared validated types. Values are normalised so 'High' / 'high' / ' HIGH ' all work."""
from typing import Annotated, Literal

from pydantic import BeforeValidator, StringConstraints


def _lower(value):
    if isinstance(value, str):
        return value.strip().lower().replace(" ", "_")
    return value


def _capitalise(value):
    if isinstance(value, str):
        return value.strip().capitalize()
    return value


Priority = Annotated[Literal["low", "medium", "high"], BeforeValidator(_lower)]
Status = Annotated[Literal["pending", "in_progress", "completed"], BeforeValidator(_lower)]
WorkingTime = Annotated[
    Literal["Morning", "Afternoon", "Evening", "Flexible"], BeforeValidator(_capitalise)
]

# Non-empty text (whitespace is stripped first, so "   " is rejected).
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
