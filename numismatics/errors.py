class BaseError(Exception):
    pass


class Undefined(BaseError):
    pass


class UnauthorizedError(BaseError):
    pass


class MissingObjects(BaseError):
    pass


class OwnerMismatch(BaseError):
    pass


class UniqueError(BaseError):
    pass
