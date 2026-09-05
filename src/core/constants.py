from enum import StrEnum


class ProviderType(StrEnum):
    LOVERSLAB = "loverslab"
    PATREON = "patreon"
    MANUAL = "manual"


class RequirementStatus(StrEnum):
    NONE = "NONE"
    RESOLVED = "RESOLVED"
    PENDING_VERIFICATION = "PENDING_VERIFICATION"


class PatreonStatus(StrEnum):
    NONE = "NONE"
    PUBLIC = "PUBLIC"
    UNLOCKED = "UNLOCKED"
    LOCKED = "LOCKED"
    UNKNOWN = "UNKNOWN"
