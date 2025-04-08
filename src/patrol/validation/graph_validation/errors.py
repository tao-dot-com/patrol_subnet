from dataclasses import dataclass

class PayloadValidationError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

class SingleNodeResponse(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

@dataclass
class ErrorPayload:
    message: str
