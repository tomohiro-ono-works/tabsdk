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
