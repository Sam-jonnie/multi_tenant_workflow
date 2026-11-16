from enum import StrEnum

from sqlalchemy import Enum


def str_enum(enum_class: type[StrEnum], length: int = 50) -> Enum:
    """Store a StrEnum as a plain VARCHAR holding the enum VALUES ('task_assigned').

    Adding a new member later needs no migration, while Python still validates it.
    """
    return Enum(
        enum_class,
        native_enum=False,
        length=length,
        values_callable=lambda cls: [member.value for member in cls],
    )