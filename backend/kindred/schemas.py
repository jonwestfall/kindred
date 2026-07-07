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


class CharacterCardProfile(CharacterBase):
    """Portable, tradeable character profile.

    The core CharacterBase fields are imported into Kindred. The source and
    creator metadata fields travel with exported files so people and LLMs can
    explain where a card came from, but they are not required for chat.
    """

    source_title: str = Field(default="", max_length=500)
    source_author: str = Field(default="", max_length=300)
    source_reference: str = Field(default="", max_length=1000)
    creator_notes: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=24)


class CharacterCardBundle(BaseModel):
    """Versioned Kindred character-card import/export file."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["kindred.character_card.v1"] = Field(
        default="kindred.character_card.v1",
        alias="schema",
    )
    exported_at: datetime | None = None
    characters: list[CharacterCardProfile] = Field(min_length=1, max_length=100)


class CharacterImportResult(BaseModel):
    """Result of importing one character-card bundle."""

    created: list[Character]
    skipped: list[str]


class LoreFactInput(BaseModel):
    """One atomic fact available for lightweight retrieval."""

    title: str = Field(default="", max_length=300)
    content: str = Field(min_length=1, max_length=4000)
    keywords: list[str] = Field(default_factory=list, max_length=24)
    tags: list[str] = Field(default_factory=list, max_length=24)
    source_reference: str = Field(default="", max_length=1000)
    weight: float = Field(default=1.0, ge=0.1, le=5)


class LorePackFile(BaseModel):
    """Versioned Kindred lore/fact-pack import/export file."""

    model_config = ConfigDict(populate_by_name=True)

    schema_: Literal["kindred.fact_pack.v1"] = Field(
        default="kindred.fact_pack.v1",
        alias="schema",
    )
    exported_at: datetime | None = None
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    source_title: str = Field(default="", max_length=500)
    source_author: str = Field(default="", max_length=300)
    source_reference: str = Field(default="", max_length=1000)
    facts: list[LoreFactInput] = Field(min_length=1, max_length=500)


class LoreFact(LoreFactInput):
    """Stored lore fact record."""

    id: int
    pack_id: int
    pack_name: str | None = None
    created_at: datetime


class LorePack(BaseModel):
    """Stored lore pack with decoded facts when requested."""

    id: int
    name: str
    description: str
    source_title: str
    source_author: str
    source_reference: str
    facts: list[LoreFact] = Field(default_factory=list)
    fact_count: int = 0
    character_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class LorePackAssignment(BaseModel):
    """Complete lore-pack assignment set for one character."""

    pack_ids: list[int] = Field(default_factory=list, max_length=100)


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


class NotificationTestRequest(BaseModel):
    """Request a logged test character message for this account's notification route."""

    character_id: int
    content: str | None = Field(default=None, max_length=500)


class NotificationTestResult(BaseModel):
    """Delivery-test metadata returned after publishing a test notification."""

    status: Literal["sent"]
    web_push_configured: bool
    subscription_count: int
    thread_id: int
    message: Message


class SettingsUpdate(BaseModel):
    """A shallow patch to one persisted settings section."""

    section: Literal["daemon", "limits", "notifications", "world_notes"]
    value: dict | str


class SystemResetRequest(BaseModel):
    """Explicit confirmation for deleting local runtime state."""

    confirm: Literal["RESET"]


class ImageGenerationRequest(BaseModel):
    """Provider-neutral image request placeholder for the MVP."""

    prompt: str = Field(min_length=1, max_length=4000)
    character_id: int | None = None
    provider: str = "openai_compatible"
    dry_run: bool = True


class LoginRequest(BaseModel):
    """Username/password login request."""

    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=500)


class SessionInfo(BaseModel):
    """Authenticated session metadata returned to the frontend."""

    username: str
    role: Literal["admin", "user"]
    user_id: int | None = None


class LoginResponse(BaseModel):
    """Bearer token and user-facing session info."""

    token: str
    session: SessionInfo


class UserCreate(BaseModel):
    """Administrator-created local user account."""

    username: str = Field(min_length=1, max_length=120)
    display_name: str = Field(default="", max_length=200)
    password: str = Field(min_length=8, max_length=500)
    disabled: bool = False
    character_ids: list[int] = Field(default_factory=list)


class UserUpdate(BaseModel):
    """Partial local user account update."""

    model_config = ConfigDict(extra="forbid")
    username: str | None = Field(default=None, min_length=1, max_length=120)
    display_name: str | None = Field(default=None, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=500)
    disabled: bool | None = None
    character_ids: list[int] | None = None


class UserOut(BaseModel):
    """Regular local user account without password material."""

    id: int
    username: str
    display_name: str
    disabled: bool
    character_ids: list[int]
    created_at: datetime
    updated_at: datetime
