# instead of crashing the system wrap the error and send it to the frontend. (to display the error to the user)


class EditorError(Exception):
    """
    Base class for all editor-related errors.
    """
    pass


class OutOfBoundsError(EditorError):
    """
    Raised when coordinates are outside the grid.
    """
    pass


class InvalidPlacementError(EditorError):
    """
    Raised when a cell type cannot be placed at a location.
    """
    pass

