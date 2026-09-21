from enum import StrEnum


class ProviderType(StrEnum):
    """Classe ProviderType : assure la gestion et l'orchestration de Providertype."""

    LOVERSLAB = "loverslab"
    PATREON = "patreon"
    MANUAL = "manual"


class RequirementStatus(StrEnum):
    """Classe RequirementStatus : assure la gestion et l'orchestration de Requirementstatus."""

    NONE = "NONE"
    RESOLVED = "RESOLVED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class PatreonStatus(StrEnum):
    """Classe PatreonStatus : assure la gestion et l'orchestration de Patreonstatus."""

    NONE = "NONE"
    PUBLIC = "PUBLIC"
    UNLOCKED = "UNLOCKED"
    LOCKED = "LOCKED"
    UNKNOWN = "UNKNOWN"
