from enum import Enum

from softioc import builder

from ._types import EpicsName


class Statuses(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2


class ConnectionStatus:
    def __init__(self, record_prefix: str):
        self.status_record_name = EpicsName(record_prefix + ":Status")
        self.status_record = builder.mbbIn(
            self.status_record_name,
            *[status.name for status in Statuses],
            initial_value=Statuses.DISCONNECTED.value,
            DESC="Connection status of the PandABox",
        )
        self.status_record.add_alias(EpicsName(record_prefix + ":STATUS"))

    def set_status(self, status: Statuses):
        self.status_record.set(status.value)

    @property
    def status(self):
        return Statuses(self.status_record.value)
