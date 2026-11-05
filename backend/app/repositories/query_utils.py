from collections.abc import Sequence
from typing import Any

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.base import ExecutableOption

from app.core.enums import SortOrder
from app.schemas.common import PageParams


def paginate[T](
    db: Session,
    stmt: Select[tuple[T]],
    params: PageParams,
    *,
    order_by: Sequence[ColumnElement[Any]],
    options: Sequence[ExecutableOption] = (),
) -> tuple[list[T], int]:
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    page_stmt = (
        stmt.options(*options)
        .order_by(*order_by)
        .offset(params.offset)
        .limit(params.page_size)
    )
    items = db.scalars(page_stmt).unique().all()
    return list(items), total


def order_by_clauses(
    column: ColumnElement[Any], order: SortOrder, tie_breaker: ColumnElement[Any]
) -> list[ColumnElement[Any]]:
    primary = column.asc() if order == SortOrder.ASC else column.desc()
    return [primary.nulls_last(), tie_breaker.asc()]