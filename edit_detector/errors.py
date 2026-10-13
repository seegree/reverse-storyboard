class AppError(Exception):
    """An actionable error suitable for display in the GUI."""


class Cancelled(AppError):
    pass
