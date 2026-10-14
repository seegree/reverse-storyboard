class AppError(Exception):
    """An actionable error suitable for display in the GUI."""


class Cancelled(AppError):
    pass


class CaptionResponseError(AppError):
    """Inference completed, but its response could not be used as a caption."""
