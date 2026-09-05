from dataclasses import dataclass


class TwbPatchError(Exception):
    """Base error for twbpatch."""


class NotFoundError(TwbPatchError):
    pass


class AmbiguousCaptionError(TwbPatchError):
    pass


class AmbiguousFormulaReferenceError(TwbPatchError):
    pass


class ValidationError(TwbPatchError):
    pass


class UnsupportedFeatureError(TwbPatchError):
    pass


class SaveError(TwbPatchError):
    pass


class DetachedModelError(TwbPatchError):
    pass


@dataclass(frozen=True)
class ResourceReference:
    resource_type: str
    resource_id: str
    location: str


class ResourceInUseError(TwbPatchError):
    def __init__(self, resource_type: str, resource_id: str, references: list[ResourceReference]):
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.references = references
        super().__init__(f"{resource_type} is in use and cannot be deleted: {resource_id}")
