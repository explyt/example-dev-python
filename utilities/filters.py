import django_filters
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django_filters.constants import EMPTY_VALUES
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from django.db import models as _models
from django.db.models import F, Value, Func, FloatField, CharField, Q

__all__ = (
    'ContentTypeFilter',
    'MultiValueArrayFilter',
    'MultiValueCharFilter',
    'MultiValueDateFilter',
    'MultiValueDateTimeFilter',
    'MultiValueDecimalFilter',
    'MultiValueMACAddressFilter',
    'MultiValueNumberFilter',
    'MultiValueTimeFilter',
    'MultiValueWWNFilter',
    'NullableCharFieldFilter',
    'NumericArrayFilter',
    'TreeNodeMultipleChoiceFilter',
    'JSONEmptyFilter',
    'JSONBooleanFilter',
)


def multivalue_field_factory(field_class):
    """
    Given a form field class, return a subclass capable of accepting multiple values. This allows us to OR on multiple
    filter values while maintaining the field's built-in validation. Example: GET /api/dcim/devices/?name=foo&name=bar
    """
    class NewField(field_class):
        widget = forms.SelectMultiple

        def to_python(self, value):
            if not value:
                return []
            field = field_class()
            return [
                # Only append non-empty values (this avoids e.g. trying to cast '' as an integer)
                field.to_python(v) for v in value if v
            ]

        def run_validators(self, value):
            for v in value:
                super().run_validators(v)

        def validate(self, value):
            for v in value:
                super().validate(v)

    return type(f'MultiValue{field_class.__name__}', (NewField,), dict())


#
# Filters
#

@extend_schema_field(OpenApiTypes.STR)
class MultiValueCharFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.CharField)


class JSONKeyCharFilter(django_filters.MultipleChoiceFilter):
    """
    Char filter for a string value stored at JSONField key.
    Supports exact/in, icontains (ic), startswith (isw) and their negations via exclude.
    """
    field_class = multivalue_field_factory(forms.CharField)

    def __init__(self, *args, json_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_key = json_key

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        
        if not self.json_key:
            return super().filter(qs, value)
        
        from django.db import models as _models
        from django.db.models import F, Value, Func, CharField, Q
        
        field_name = self.field_name
        json_path = f'$.{self.json_key}'
        jtype = Func(F(field_name), Value(json_path), function='json_type', output_field=CharField())
        jraw = Func(F(field_name), Value(json_path), function='json_extract', output_field=_models.TextField())
        jtxt = _models.functions.Cast(jraw, CharField())
        qs = qs.annotate(_json_type=jtype, _json_txt=jtxt)
        
        vals = value if isinstance(value, (list, tuple)) else [value]
        vals = [str(v) for v in vals]
        guard = Q(_json_type='text')
        lookup = getattr(self, 'lookup_expr', 'exact') or 'exact'
        cond = Q()
        
        # Map lookup expressions to Q field lookups
        lookup_map = {
            'exact': '_json_txt__in',
            'in': '_json_txt__in',
            'icontains': '_json_txt__icontains',
            'ic': '_json_txt__icontains',
            'istartswith': '_json_txt__istartswith',
            'startswith': '_json_txt__istartswith',
            'isw': '_json_txt__istartswith',
            'iendswith': '_json_txt__iendswith',
            'endswith': '_json_txt__iendswith',
            'iew': '_json_txt__iendswith',
            'iexact': '_json_txt__iexact',
            'ie': '_json_txt__iexact',
        }
        
        field_lookup = lookup_map.get(lookup, '_json_txt__in')
        
        if lookup in ('exact', 'in'):
            cond = Q(**{field_lookup: vals})
        else:
            # For other lookups, OR multiple values
            cond = Q()
            for v in vals:
                cond |= Q(**{field_lookup: v})
        
        qobj = guard & cond
        if getattr(self, 'exclude', False):
            return qs.exclude(qobj)
        return qs.filter(qobj)


@extend_schema_field(OpenApiTypes.DATE)
class MultiValueDateFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.DateField)


class JSONDateFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.DateField)

    def __init__(self, *args, json_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_key = json_key

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        
        if not self.json_key:
            return super().filter(qs, value)
        
        field_name = self.field_name
        model = qs.model
        field = model._meta.get_field(field_name)
        table = model._meta.db_table
        column = f'"{table}"."{field.column}"'
        json_path = f'$.{self.json_key}'
        lookup = getattr(self, 'lookup_expr', 'exact') or 'exact'
        negate = bool(getattr(self, 'exclude', False))
        values = value if isinstance(value, (list, tuple)) else [value]
        values = [str(v) for v in values]

        not_null_clause = f"json_extract({column}, ?) IS NOT NULL"
        cast_expr = f"CAST(json_extract({column}, ?) AS TEXT)"

        def build_or(op):
            clauses = []
            params = []
            for v in values:
                clauses.append(f"{cast_expr} {op} ?")
                params.extend([json_path, v])
            return '(' + ' OR '.join(clauses) + ')', params

        if lookup in ('exact', 'in'):
            body_sql, p = build_or('=')
            sql = f"({not_null_clause}) AND {body_sql}"
            params = [json_path] + p
            if negate:
                placeholders = ', '.join(['?'] * len(values))
                sql = f"({not_null_clause}) AND {cast_expr} NOT IN ({placeholders})"
                params = [json_path, json_path] + values
        elif lookup == 'gt':
            body_sql, p = build_or('>')
            sql = f"({not_null_clause}) AND {body_sql}"
            params = [json_path] + p
            if negate:
                body_sql, p = build_or('<=')
                sql = f"({not_null_clause}) AND {body_sql}"
                params = [json_path] + p
        elif lookup == 'gte':
            body_sql, p = build_or('>=')
            sql = f"({not_null_clause}) AND {body_sql}"
            params = [json_path] + p
            if negate:
                body_sql, p = build_or('<')
                sql = f"({not_null_clause}) AND {body_sql}"
                params = [json_path] + p
        elif lookup == 'lt':
            body_sql, p = build_or('<')
            sql = f"({not_null_clause}) AND {body_sql}"
            params = [json_path] + p
            if negate:
                body_sql, p = build_or('>=')
                sql = f"({not_null_clause}) AND {body_sql}"
                params = [json_path] + p
        elif lookup == 'lte':
            body_sql, p = build_or('<=')
            sql = f"({not_null_clause}) AND {body_sql}"
            params = [json_path] + p
            if negate:
                body_sql, p = build_or('>')
                sql = f"({not_null_clause}) AND {body_sql}"
                params = [json_path] + p
        else:
            body_sql, p = build_or('=')
            sql = f"({not_null_clause}) AND {body_sql}"
            params = [json_path] + p

        return qs.extra(where=[sql], params=params)


@extend_schema_field(OpenApiTypes.DATETIME)
class MultiValueDateTimeFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.DateTimeField)


@extend_schema_field(OpenApiTypes.INT32)
class MultiValueNumberFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.IntegerField)


class _JSONNumericFilterMixin:
    """Base mixin for JSON numeric filters (Integer and Decimal)."""
    
    def _filter_json_numeric(self, qs, value):
        """Common logic for filtering numeric values in JSON fields."""
        if value in EMPTY_VALUES:
            return qs
        
        if not self.json_key:
            return super().filter(qs, value)
        
        field_name = self.field_name
        json_path = f'$.{self.json_key}'
        jtype = Func(F(field_name), Value(json_path), function='json_type', output_field=CharField())
        jraw = Func(F(field_name), Value(json_path), function='json_extract', output_field=_models.TextField())
        jnum = _models.functions.Cast(jraw, FloatField())
        qs = qs.annotate(_json_type=jtype, _json_num=jnum)

        values = value if isinstance(value, (list, tuple)) else [value]
        nums = []
        for v in values:
            try:
                nums.append(float(v))
            except (ValueError, TypeError):
                continue
        if not nums:
            return qs.none()

        guard = Q(_json_type__in=['real', 'integer'])
        lookup = getattr(self, 'lookup_expr', 'exact') or 'exact'
        
        # Build condition based on lookup
        if lookup in ('exact', 'in'):
            cond = Q(_json_num__in=nums)
        elif lookup in ('gt', 'gte', 'lt', 'lte'):
            cond = Q()
            for n in nums:
                cond |= Q(**{f'_json_num__{lookup}': n})
        else:
            cond = Q(_json_num__in=nums)

        qobj = guard & cond
        return qs.exclude(qobj) if getattr(self, 'exclude', False) else qs.filter(qobj)


class JSONIntegerFilter(_JSONNumericFilterMixin, django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.IntegerField)

    def __init__(self, *args, json_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_key = json_key

    def filter(self, qs, value):
        return self._filter_json_numeric(qs, value)


@extend_schema_field(OpenApiTypes.DECIMAL)
class MultiValueDecimalFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.DecimalField)


class JSONDecimalFilter(_JSONNumericFilterMixin, django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.DecimalField)

    def __init__(self, *args, json_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_key = json_key

    def filter(self, qs, value):
        return self._filter_json_numeric(qs, value)


@extend_schema_field(OpenApiTypes.TIME)
class MultiValueTimeFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.TimeField)


@extend_schema_field(OpenApiTypes.STR)
class MultiValueArrayFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.CharField)

    def __init__(self, *args, lookup_expr='contains', **kwargs):
        # Set default lookup_expr to 'contains'
        super().__init__(*args, lookup_expr=lookup_expr, **kwargs)

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        values = list(value)
        has_null_token = any(isinstance(v, str) and v.lower() == 'null' for v in values)
        # Remove 'null' token from values passed to default handler
        clean_values = [v for v in values if not (isinstance(v, str) and v.lower() == 'null')]

        from django.db.models import Q
        base_qs = qs
        if has_null_token:
            # Match either explicit JSON null (contains [None]) or field is NULL
            null_q = Q(**{f"{self.field_name}__contains": [None]}) | Q(**{f"{self.field_name}__isnull": True})
            base_qs = base_qs.filter(null_q)

        if clean_values:
            base_qs = super().filter(base_qs, clean_values)

        return base_qs

    def get_filter_predicate(self, v):
        # Translate string 'null' token to actual None sentinel for base behavior
        if isinstance(v, str) and v.lower() == 'null':
            v = None
        # If filtering for null values, ignore lookup_expr
        if v is None:
            return {self.field_name: None}
        return super().get_filter_predicate(v)


class JSONKeyArrayFilter(django_filters.MultipleChoiceFilter):
    """
    Filter for JSON array at a given key inside JSONField.
    Supports:
    - contains values: EXISTS json_each(base, '$.key') matches any provided value (string)
    - 'null' token: matches when the key value is NULL (missing or explicit null)
    """
    field_class = multivalue_field_factory(forms.CharField)

    def __init__(self, *args, json_key=None, **kwargs):
        kwargs.setdefault('lookup_expr', 'contains')
        super().__init__(*args, **kwargs)
        self.json_key = json_key

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        
        values = list(value)
        has_null_token = any(isinstance(v, str) and v.lower() == 'null' for v in values)
        clean_values = [v for v in values if not (isinstance(v, str) and v.lower() == 'null')]

        if not self.json_key:
            if clean_values:
                return super().filter(qs, clean_values)
            return qs
        
        model = qs.model
        field = model._meta.get_field(self.field_name)
        table = model._meta.db_table
        column = f'"{table}"."{field.column}"'
        json_path = f'$.{self.json_key}'
        where_parts = []
        params = []
        
        if clean_values:
            clauses = []
            for s in clean_values:
                clauses.append(
                    f"EXISTS (SELECT 1 FROM json_each({column}, ?) je WHERE CAST(je.value AS TEXT)=?)"
                )
                params.extend([json_path, str(s)])
            where_parts.append('(' + ' OR '.join(clauses) + ')')
        
        if has_null_token:
            where_parts.append(
                f"json_type({column}, ?) = 'null' OR EXISTS (SELECT 1 FROM json_each({column}, ?) je WHERE je.value IS NULL)"
            )
            params.extend([json_path, json_path])
        
        if not where_parts:
            return qs
        
        return qs.extra(where=[' AND '.join(where_parts)], params=params)


@extend_schema_field(OpenApiTypes.STR)
class MultiValueMACAddressFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.CharField)

    def filter(self, qs, value):
        try:
            return super().filter(qs, value)
        except ValidationError:
            return qs.none()


@extend_schema_field(OpenApiTypes.STR)
class MultiValueWWNFilter(django_filters.MultipleChoiceFilter):
    field_class = multivalue_field_factory(forms.CharField)


@extend_schema_field(OpenApiTypes.STR)
class TreeNodeMultipleChoiceFilter(django_filters.ModelMultipleChoiceFilter):
    """
    Filters for a set of Models, including all descendant models within a Tree.  Example: [<Region: R1>,<Region: R2>]
    """
    def get_filter_predicate(self, v):
        # Null value filtering
        if v is None:
            return {f"{self.field_name}__isnull": True}
        return super().get_filter_predicate(v)

    def filter(self, qs, value):
        value = [node.get_descendants(include_self=True) if not isinstance(node, str) else node for node in value]
        return super().filter(qs, value)


class NullableCharFieldFilter(django_filters.CharFilter):
    """
    Allow matching on null field values by passing a special string used to signify NULL.
    """
    def filter(self, qs, value):
        if value != settings.FILTERS_NULL_CHOICE_VALUE:
            return super().filter(qs, value)
        qs = self.get_method(qs)(**{'{}__isnull'.format(self.field_name): True})
        return qs.distinct() if self.distinct else qs


class JSONEmptyFilter(django_filters.BooleanFilter):
    """
    Boolean filter to test emptiness of a JSON value at a given JSONField path.

    Usage:
    - field_name must be the JSONField itself (e.g. 'custom_field_data')
    - pass json_key='cf10' to address the concrete key inside JSON

    Semantics:
    - Empty when value is NULL (missing key or explicit null)
    - Empty when value is an array with length 0
    - Not empty when value exists and array length > 0
    """
    def __init__(self, *args, json_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_key = json_key

    def filter(self, qs, value):
        from django.db.models import F, Value, Func, IntegerField, BooleanField, Case, When, CharField
        from django.db import models as _models
        
        if value in EMPTY_VALUES:
            return qs
        
        is_true = bool(value)
        field_name = self.field_name

        if not self.json_key:
            if is_true:
                return qs.filter(**{f'{field_name}__isnull': True})
            else:
                return qs.exclude(**{f'{field_name}__isnull': True})
        
        json_path = f'$.{self.json_key}'
        extracted = Func(F(field_name), Value(json_path), function='json_extract', output_field=_models.TextField())
        qs = qs.annotate(_json_val=extracted)
        jtype = Func(F(field_name), Value(json_path), function='json_type', output_field=CharField())
        qs = qs.annotate(_json_type=jtype)
        arr_len = Func(F(field_name), Value(json_path), function='json_array_length', output_field=IntegerField())
        qs = qs.annotate(_json_array_len=arr_len)

        is_empty = Case(
            When(_json_val__isnull=True, then=Value(True)),
            When(_json_type='array', _json_array_len=0, then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
        qs = qs.annotate(_json_empty=is_empty)
        return qs.filter(_json_empty=True) if is_true else qs.filter(_json_empty=False)


class JSONBooleanFilter(django_filters.BooleanFilter):
    """
    Boolean filter against a JSONField key.
    Uses json_extract(base_field, '$.<key>') which returns 1 for true and 0 for false.
    """
    def __init__(self, *args, json_key=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.json_key = json_key

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        
        is_true = bool(value)
        field_name = self.field_name
        
        if not self.json_key:
            return qs.filter(**{f'{field_name}': is_true})
        
        from django.db.models import F, IntegerField
        from utilities.query_functions import JSONExtract
        
        extracted = JSONExtract(F(field_name), f'$.{self.json_key}', output_field=IntegerField())
        target = 1 if is_true else 0
        return qs.annotate(_json_bool=extracted).filter(_json_bool=target)


class NumericArrayFilter(django_filters.NumberFilter):
    """
    Filter based on the presence of an integer within an ArrayField or JSON list.
    """
    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        
        try:
            return qs.filter(**{f"{self.field_name}__contains": [int(value)]})
        except (ValueError, TypeError):
            return qs.none()


class JSONIntegerArrayContainsFilter(django_filters.MultipleChoiceFilter):
    """
    JSON array containment for a JSONField key: checks if array contains ANY of provided integers.
    Uses json_each(base, '$.key').
    """
    field_class = multivalue_field_factory(forms.IntegerField)

    def __init__(self, *args, json_key=None, **kwargs):
        kwargs.setdefault('lookup_expr', 'contains')
        super().__init__(*args, **kwargs)
        self.json_key = json_key

    def filter(self, qs, value):
        if value in EMPTY_VALUES:
            return qs
        
        if not self.json_key:
            return qs.filter(**{f"{self.field_name}__contains": list(value)})
        
        vals = value if isinstance(value, (list, tuple)) else [value]
        ints = []
        for v in vals:
            try:
                ints.append(int(v))
            except (ValueError, TypeError):
                continue
        if not ints:
            return qs.none()
        
        model = qs.model
        field = model._meta.get_field(self.field_name)
        table = model._meta.db_table
        column = f'"{table}"."{field.column}"'
        json_path = f'$.{self.json_key}'
        clauses = []
        params = []
        guard = f"json_type({column}, ?) = 'array'"
        params.append(json_path)
        
        for n in ints:
            clauses.append(
                f"EXISTS (SELECT 1 FROM json_each({column}, ?) je WHERE CAST(je.value AS INTEGER)=?)"
            )
            params.extend([json_path, n])
        
        where = f"({guard}) AND (" + " OR ".join(clauses) + ")"
        return qs.extra(where=[where], params=params)


class ContentTypeFilter(django_filters.CharFilter):
    """
    Allow specifying a ContentType by <app_label>.<model> (e.g. "dcim.site").

    Note: Some request parsers/widgets may pass a dict-like value (e.g. {"value": "app.model"}
    or {"app_label": "app", "model": "model"}). To be resilient across backends, normalize
    such inputs instead of raising AttributeError on value.lower().
    """
    def filter(self, qs, value):
        # Short-circuit on empty values
        if value in EMPTY_VALUES:
            return qs

        # Normalize dict-like inputs that may come from UI widgets or DRF parsers
        if isinstance(value, dict):
            if 'value' in value and isinstance(value['value'], str):
                value = value['value']
            elif 'app_label' in value and 'model' in value:
                app_label = str(value['app_label']).lower()
                model = str(value['model']).lower()
                return qs.filter(
                    **{
                        f'{self.field_name}__app_label': app_label,
                        f'{self.field_name}__model': model,
                    }
                )
            else:
                # Unknown dict format – ignore filter safely
                return qs

        # If we made it here and still don't have a string, ignore filter
        if not isinstance(value, str):
            return qs

        try:
            app_label, model = value.lower().split('.')
        except ValueError:
            return qs.none()
        return qs.filter(
            **{
                f'{self.field_name}__app_label': app_label,
                f'{self.field_name}__model': model
            }
        )
