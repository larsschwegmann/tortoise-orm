import enum

from pypika_tortoise import functions
from pypika_tortoise.enums import SqlTypes
from pypika_tortoise.terms import BasicCriterion, Criterion
from pypika_tortoise.utils import format_quotes
from pypika_tortoise.functions import Cast

from tortoise import Model
from tortoise.backends.base.executor import BaseExecutor
from tortoise.contrib.mysql.json_functions import (
    mysql_json_contained_by,
    mysql_json_contains,
    mysql_json_filter,
)
from tortoise.contrib.mysql.search import SearchCriterion
from tortoise.fields import BigIntField, IntField, SmallIntField
from tortoise.filters import (
    Like,
    Term,
    ValueWrapper,
    contains,
    ends_with,
    insensitive_contains,
    insensitive_ends_with,
    insensitive_exact,
    insensitive_starts_with,
    json_contained_by,
    json_contains,
    json_filter,
    posix_regex,
    search,
    starts_with,
)


class MySQLRegexpComparators(enum.Enum):
    REGEXP = " REGEXP "

class StrWrapper(ValueWrapper):
    """
    Naive str wrapper that doesn't use the monkey-patched pypika ValueWrapper for MySQL
    """

    def get_value_sql(self, **kwargs) -> str:
        quote_char = kwargs.get("secondary_quote_char") or ""
        value = self.value.replace(quote_char, quote_char * 2)
        return format_quotes(value, quote_char)


def escape_like(val: str) -> str:
    return val.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def mysql_contains(field: Term, value: str) -> Criterion:
    return Like(
        functions.Cast(field, SqlTypes.CHAR), StrWrapper(f"%{escape_like(value)}%"), escape=""
    )


def mysql_starts_with(field: Term, value: str) -> Criterion:
    return Like(
        functions.Cast(field, SqlTypes.CHAR), StrWrapper(f"{escape_like(value)}%"), escape=""
    )


def mysql_ends_with(field: Term, value: str) -> Criterion:
    return Like(
        functions.Cast(field, SqlTypes.CHAR), StrWrapper(f"%{escape_like(value)}"), escape=""
    )


def mysql_insensitive_exact(field: Term, value: str) -> Criterion:
    return functions.Upper(functions.Cast(field, SqlTypes.CHAR)).eq(functions.Upper(str(value)))


def mysql_insensitive_contains(field: Term, value: str) -> Criterion:
    return Like(
        functions.Upper(functions.Cast(field, SqlTypes.CHAR)),
        functions.Upper(StrWrapper(f"%{escape_like(value)}%")),
        escape="",
    )


def mysql_insensitive_starts_with(field: Term, value: str) -> Criterion:
    return Like(
        functions.Upper(functions.Cast(field, SqlTypes.CHAR)),
        functions.Upper(StrWrapper(f"{escape_like(value)}%")),
        escape="",
    )


def mysql_insensitive_ends_with(field: Term, value: str) -> Criterion:
    return Like(
        functions.Upper(functions.Cast(field, SqlTypes.CHAR)),
        functions.Upper(StrWrapper(f"%{escape_like(value)}")),
        escape="",
    )


def mysql_search(field: Term, value: str) -> SearchCriterion:
    return SearchCriterion(field, expr=StrWrapper(value))


def mysql_posix_regex(field: Term, value: str) -> BasicCriterion:
    return BasicCriterion(MySQLRegexpComparators.REGEXP, Cast(field, SqlTypes.VARCHAR), StrWrapper(value))  # type:ignore[arg-type]


class MySQLExecutor(BaseExecutor):
    FILTER_FUNC_OVERRIDE = {
        contains: mysql_contains,
        starts_with: mysql_starts_with,
        ends_with: mysql_ends_with,
        insensitive_exact: mysql_insensitive_exact,
        insensitive_contains: mysql_insensitive_contains,
        insensitive_starts_with: mysql_insensitive_starts_with,
        insensitive_ends_with: mysql_insensitive_ends_with,
        search: mysql_search,
        json_contains: mysql_json_contains,
        json_contained_by: mysql_json_contained_by,
        json_filter: mysql_json_filter,
        posix_regex: mysql_posix_regex,
    }
    EXPLAIN_PREFIX = "EXPLAIN FORMAT=JSON"

    async def _process_insert_result(self, instance: Model, results: int) -> None:
        pk_field_object = self.model._meta.pk
        if (
            isinstance(pk_field_object, (SmallIntField, IntField, BigIntField))
            and pk_field_object.generated
        ):
            instance.pk = results

        # MySQL can only generate a single ROWID
        #   so if any other primary key, it won't generate what we want.
