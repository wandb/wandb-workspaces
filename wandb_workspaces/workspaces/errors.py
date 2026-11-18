class SpecVersionError(Exception): ...


class UnsupportedViewError(Exception): ...


class ViewSpecConflictError(Exception):
    """The workspace changed on the server since it was loaded, so the save was refused.

    Reload it with `Workspace.from_url`, reapply your edits, and save again.
    """
