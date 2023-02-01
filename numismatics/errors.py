class BaseError(Exception):
    pass


class UndefinedError(BaseError):
    pass


class UnauthorizedError(BaseError):
    pass


class MissingObjectsError(BaseError):
    pass


class OwnerMismatchError(BaseError):
    pass


class UniqueError(BaseError):
    pass


class SelfTransferError(BaseError):
    pass
