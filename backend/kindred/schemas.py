"""Pydantic request and response contracts for the public API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


BackendName = Literal["ollama", "llamacpp", "openai_compatible"]


class CharacterBase(BaseModel):
    """Editable character profile fields."""

    name: str = Field(min_length=1, max_length=120)
    avatar_url: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=4000)
    personality: str = Field(default="", max_length=8000)
    speaking_style: str = Field(default="", max_length=4000)
    backstory: str = Field(default="", max_length=12000)
    goals: str = Field(default="", max_length=6000)
    boundaries: str = Field(default="", max_length=6000)
    backend: BackendName = "ollama"
    model: str = Field(default="llama3.2:1b", min_length=1, max_length=200)
    temperature: float = Field(default=0.7, ge=0, le=2)
    initiative_frequency: float = Field(
        default=1.0,
        ge=0,
        le=24,
        description="Expected autonomous messages per day before quiet-hour and cooldown checks.",
    )
    cooldown_minutes: int = Field(default=240, ge=15, le=10080)


class CharacterCreate(CharacterBase):
    """Payload for creating a character."""


class CharacterUpdate(BaseModel):
    """Partial character update payload."""

    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    avatar_url: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=4000)
    personality: str | None = Field(default=None, max_length=8000)
    speaking_style: str | None = Field(default=None, max_length=4000)
    backstory: str | None = Field(default=None, max_length=12000)
    goals: str | None = Field(default=None, max_length=6000)
    boundaries: str | None = Field(default=None, max_length=6000)
    backend: BackendName | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0, le=2)
    initiative_frequency: float | None = Field(default=None, ge=0, le=24)
    cooldown_minutes: int | None = Field(default=None, ge=15, le=10080)


class Character(CharacterBase):
    """Stored character record."""

    id: int
    created_at: datetime
    updated_at: datetime


class ThreadCreate(BaseModel):
    """Create a conversation thread for one character."""

    character_id: int
    title: str = Field(default="Conversation", min_length=1, max_length=200)


class ChatRequest(BaseModel):
    """A user-authored message."""

    content: str = Field(min_length=1, max_length=20000)


class Message(BaseModel):
    """Stored conversation message with writer/research metadata."""

    id: int
    thread_id: int
    character_id: int
    sender: Literal["user", "character", "system"]
    content: str
    timestamp: datetime
    backend: str
    model: str
    prompt_context_summary: str
    character_rationale: str
    initiated: bool


class SettingsUpdate(BaseModel):
    """A shallow patch to one persisted settings section."""

    section: Literal["daemon", "limits", "notifications", "world_notes"]
    value: dict | str


class ImageGenerationRequest(BaseModel):
    """Provider-neutral image request placeholder for the MVP."""

    prompt: str = Field(min_length=1, max_length=4000)
    character_id: int | None = None
    provider: str = "openai_compatible"
    dry_run: bool = True

