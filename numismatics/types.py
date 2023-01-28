from enum import Enum


class StatusTransfer(str, Enum):
    initial = "initial"
    approved = "approved"
    declined = "declined"
