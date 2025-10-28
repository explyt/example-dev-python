from django.db import models
from django.db.models import Func, F

from utilities.sqlite_collations import _collate_natural

__all__ = (
    'CollateAsChar',
    'CollateNatural',
    'EmptyGroupByJSONBAgg',
    'JSONExtract',
)


class CollateAsChar(Func):
    """SQLite collation as plain character string using BINARY."""
    def __init__(self, expression, **extra):
        # Allow passing a field name as a string
        if isinstance(expression, str):
            expression = F(expression)
        super().__init__(expression, **extra)

    def as_sql(self, compiler, connection, **extra_context):
        self.template = '%(expressions)s COLLATE BINARY'
        return super().as_sql(compiler, connection, **extra_context)


class CollateNatural(Func):
    """SQLite natural sort collation registered at runtime."""
    def __init__(self, expression, **extra):
        if isinstance(expression, str):
            expression = F(expression)
        super().__init__(expression, **extra)

    def as_sql(self, compiler, connection, **extra_context):
        self.template = '%(expressions)s COLLATE natural_sort'
        return super().as_sql(compiler, connection, **extra_context)


class JSONExtract(Func):
    """SQLite json_extract helper with correctly quoted JSON path."""
    function = 'json_extract'
    output_field = models.TextField()

    def __init__(self, expression, path, output_field=None, **extra):
        if isinstance(expression, str):
            expression = F(expression)
        self.json_path = path
        if output_field is None:
            output_field = self.output_field
        super().__init__(expression, output_field=output_field, **extra)

    def as_sql(self, compiler, connection, **extra_context):
        self.template = "json_extract(%(expressions)s, '%(json_path)s')"
        extra_context.update({'json_path': self.json_path})
        return super().as_sql(compiler, connection, **extra_context)


class EmptyGroupByJSONBAgg(Func):
    """
    SQLite aggregation using JSON1 json_group_array() to aggregate rows into a JSON array.
    - If called with one expression (data), aggregates raw values.
    - If called with three expressions (weight, name, data), aggregates JSON objects {'w': weight, 'n': name, 'd': data}
      to preserve ordering metadata for post-processing.
    """
    contains_aggregate = True
    output_field = models.TextField()

    def as_sql(self, compiler, connection, **extra_context):
        function = 'json_group_array'
        if len(self.source_expressions) == 3:
            # Compile each expression separately and build json_object('w', w, 'n', n, 'd', d)
            sqls = []
            params = []
            for expr in self.source_expressions:
                s, p = compiler.compile(expr)
                sqls.append(s)
                params.extend(p)
            inner_sql = f"json_object('w', {sqls[0]}, 'n', {sqls[1]}, 'd', {sqls[2]})"
            sql = f"{function}({inner_sql})"
            return sql, params
        else:
            # Default: aggregate the single expression as-is
            self.function = function
            self.template = '%(function)s(%(expressions)s)'
            return super().as_sql(compiler, connection, **extra_context)
