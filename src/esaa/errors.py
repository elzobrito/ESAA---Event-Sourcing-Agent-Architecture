from __future__ import annotations


class ESAAError(Exception):
    """Domain error with a stable error code.

    penalizes_counter=False indica que a rejeicao nao deve incrementar o
    contador de tentativas (ex.: PRIOR_STATUS_MISMATCH e lag de contexto).
    """

    def __init__(self, code: str, message: str, penalizes_counter: bool = True) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.penalizes_counter = penalizes_counter


class CorruptedStoreError(ESAAError):
    pass
