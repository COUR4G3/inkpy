class StoryException(RuntimeError):
    pass


class ExternalBindingsValidationError(StoryException):
    def __init__(self, missing: set, allow_external_function_fallbacks: bool = True):
        message = "Missing function binding(s) for external(s): '"
        message += "', '".join(missing)

        if self.allow_external_function_fallbacks:
            message += "' (ink fallbacks disabled)"
        else:
            message += "', and no fallback ink function(s) found."

        self.allow_external_function_fallbacks = allow_external_function_fallbacks
        self.missing = missing

        super().__init__(message)
