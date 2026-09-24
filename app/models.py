"""Pydantic mirror of the Go AIContext JSON contract (cloud9-api)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _ExtraModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class SignalFreshness(_ExtraModel):
    tier: str
    nominal_lag_seconds: float = Field(alias="nominalLagSeconds")
    source: str | None = None


class Fact(_ExtraModel):
    ref: str
    kind: str
    component: str | None = None
    value: Any = None
    freshness: SignalFreshness | None = None
    timestamp: datetime | None = None


class SignalDescriptor(_ExtraModel):
    name: str
    component: str
    unit: str
    semantic: str
    meaning: str
    freshness: SignalFreshness


class ConfigCause(_ExtraModel):
    role: str
    instance: str | None = None
    key: str
    value: Any = None


class ViolationRollup(_ExtraModel):
    id: str
    count: int
    detail: dict[str, str] | None = None
    caused_by: list[ConfigCause] | None = Field(default=None, alias="causedBy")


class Precondition(_ExtraModel):
    role: str | None = None
    key: str | None = None
    any_of: list[str] | None = Field(default=None, alias="anyOf")


class Mechanism(_ExtraModel):
    id: str
    trigger_rules: list[str] = Field(alias="triggerRules")
    precondition: Precondition = Field(default_factory=Precondition)
    causal_chain: list[str] = Field(alias="causalChain")
    suggestion: str


class InstanceConfig(_ExtraModel):
    id: str = Field(alias="ID")
    type: str = Field(alias="Type")
    engine: str = Field(default="", alias="Engine")
    settings: dict[str, Any] = Field(default_factory=dict, alias="Settings")


class DesignConfig(_ExtraModel):
    template: str = Field(alias="Template")
    roles: dict[str, list[InstanceConfig]] = Field(default_factory=dict, alias="Roles")


class InstanceInternal(_ExtraModel):
    id: str
    type: str | None = None
    engine: str | None = None
    signals: dict[str, Any] = Field(default_factory=dict)
    engine_extras: dict[str, Any] | None = Field(default=None, alias="engineExtras")
    freshness: dict[str, SignalFreshness] | None = None


class ComponentInternal(_ExtraModel):
    instances: list[InstanceInternal] = Field(default_factory=list)


class Run(_ExtraModel):
    role: str
    design_config: DesignConfig = Field(alias="designConfig")
    facts: list[Fact] = Field(default_factory=list)
    descriptors: list[SignalDescriptor] = Field(default_factory=list)
    component_internals: dict[str, ComponentInternal] = Field(
        default_factory=dict, alias="componentInternals"
    )
    violations: list[ViolationRollup] = Field(default_factory=list)
    mechanisms: list[Mechanism] | None = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    trajectories: dict[str, Any] = Field(default_factory=dict)


class AIContext(_ExtraModel):
    schema_version: int = Field(alias="schemaVersion")
    catalog_version: str = Field(alias="catalogVersion")
    session_id: str = Field(alias="sessionId")
    runs: list[Run] = Field(default_factory=list)


class ProposedMechanismClaim(_ExtraModel):
    trigger: str
    config_precondition: str | None = Field(default=None, alias="config_precondition")
    precondition: Precondition | None = None
    causal_chain: list[str] = Field(default_factory=list, alias="causalChain")


class Claim(_ExtraModel):
    scope: str
    components: list[str] = Field(default_factory=list)
    aspect: str
    text: str
    fact_refs: list[str] = Field(default_factory=list, alias="factRefs")
    grounding: str
    mechanism_id: str | None = Field(default=None, alias="mechanismId")
    proposed_mechanism: ProposedMechanismClaim | None = Field(
        default=None, alias="proposedMechanism"
    )
    confidence: str | None = None
    observed_gap_seconds: float | None = Field(default=None, alias="observedGapSeconds")


class PostmortemLLMOutput(_ExtraModel):
    claims: list[Claim] = Field(default_factory=list)
    summary: str = ""
    insufficient_evidence: list[str] = Field(default_factory=list, alias="insufficientEvidence")


class PostmortemResponse(_ExtraModel):
    status: str = "ok"
    claims: list[Claim] = Field(default_factory=list)
    summary: str = ""
    insufficient_evidence: list[str] = Field(default_factory=list, alias="insufficientEvidence")
    schema_version: int = Field(default=1, alias="schemaVersion")
    catalog_version: str = Field(default="", alias="catalogVersion")
    prompt_version: str = Field(default="postmortem-v1", alias="promptVersion")
    model: str = Field(default="none")
