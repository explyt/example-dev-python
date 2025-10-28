from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _
from netaddr import AddrFormatError, EUI, eui64_unix_expanded, mac_unix_expanded

from .lookups import PathContains

__all__ = (
    'MACAddressField',
    'PathField',
    'WWNField',
)


# Custom dialects for uppercase MAC/WWN addresses
class mac_unix_expanded_uppercase(mac_unix_expanded):
    """MAC address dialect with uppercase hex digits."""
    word_fmt = '%.2X'


class eui64_unix_expanded_uppercase(eui64_unix_expanded):
    """EUI-64 (WWN) dialect with uppercase hex digits."""
    word_fmt = '%.2X'


# Custom dialects for lowercase MAC/WWN addresses (for SQLite compatibility)
class mac_unix_expanded_lowercase(mac_unix_expanded):
    """MAC address dialect with lowercase hex digits."""
    word_fmt = '%.2x'


class eui64_unix_expanded_lowercase(eui64_unix_expanded):
    """EUI-64 (WWN) dialect with lowercase hex digits."""
    word_fmt = '%.2x'


class MACAddressField(models.Field):

    description = 'MAC Address field'

    def python_type(self):
        return EUI

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def get_internal_type(self):
        return 'CharField'

    def to_python(self, value):
        if value is None:
            return value
        if type(value) is str:
            value = value.replace(' ', '')
        try:
            return EUI(value, version=48, dialect=mac_unix_expanded)
        except AddrFormatError:
            raise ValidationError(_("Invalid MAC address format: %(value)s") % {'value': value})

    def db_type(self, connection):
        return 'VARCHAR(18)'

    def get_prep_value(self, value):
        if not value:
            return None
        if type(value) is str:
            value = value.replace(' ', '')
        try:
            eui = EUI(value, version=48, dialect=mac_unix_expanded_lowercase)
        except AddrFormatError:
            raise ValidationError(_("Invalid MAC address format: %(value)s") % {'value': value})
        return str(eui)


class WWNField(models.Field):
    description = 'World Wide Name field'

    def python_type(self):
        return EUI

    def from_db_value(self, value, expression, connection):
        return self.to_python(value)

    def get_internal_type(self):
        return 'CharField'

    def to_python(self, value):
        if value is None:
            return value
        try:
            return EUI(value, version=64, dialect=eui64_unix_expanded)
        except AddrFormatError:
            raise ValidationError(_("Invalid WWN format: %(value)s") % {'value': value})

    def db_type(self, connection):
        return 'VARCHAR(23)'

    def get_prep_value(self, value):
        if not value:
            return None
        try:
            eui = EUI(value, version=64, dialect=eui64_unix_expanded_lowercase)
        except AddrFormatError:
            raise ValidationError(_("Invalid WWN format: %(value)s") % {'value': value})
        return str(eui)


class PathField(models.JSONField):
    """
    SQLite-compatible JSONField storing a list of object identifiers.

    Stores a list of strings in format: ['ct_id:object_id', 'ct_id:object_id', ...]
    Example: ['10:123', '20:456']

    This field is used by CablePath to store the flattened list of nodes in a cable path.
    Each node is represented as 'ContentType_ID:Object_ID'.
    """
    description = "Path field (list of object identifiers)"

    def __init__(self, **kwargs):
        kwargs.setdefault('default', list)
        super().__init__(**kwargs)

    def deconstruct(self):
        """Return a 4-tuple for migrations."""
        name, path, args, kwargs = super().deconstruct()
        # Remove default from kwargs if it's list (it's our default)
        if kwargs.get('default') == list:
            del kwargs['default']
        return name, path, args, kwargs

    def validate(self, value, model_instance):
        """Validate that value is a list of strings in correct format."""
        super().validate(value, model_instance)

        if value is None:
            return

        if not isinstance(value, list):
            raise ValidationError(
                _('PathField value must be a list, got %(type)s'),
                params={'type': type(value).__name__},
                code='invalid_type'
            )

        for item in value:
            if not isinstance(item, str):
                raise ValidationError(
                    _('PathField items must be strings, got %(type)s'),
                    params={'type': type(item).__name__},
                    code='invalid_item_type'
                )

            # Validate format: 'ct_id:object_id' where both are integers
            if ':' not in item:
                raise ValidationError(
                    _('PathField items must be in format "ct_id:object_id", got %(value)s'),
                    params={'value': item},
                    code='invalid_format'
                )

            parts = item.split(':')
            if len(parts) != 2:
                raise ValidationError(
                    _('PathField items must be in format "ct_id:object_id", got %(value)s'),
                    params={'value': item},
                    code='invalid_format'
                )

            # Validate that both parts are numeric
            try:
                int(parts[0])
                int(parts[1])
            except ValueError:
                raise ValidationError(
                    _('PathField items must contain numeric IDs, got %(value)s'),
                    params={'value': item},
                    code='invalid_format'
                )

    def get_prep_value(self, value):
        """Convert Python list to JSON for database."""
        if value is None:
            return None
        # If value is a string, wrap it in a list (defensive programming)
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            raise ValidationError(f'PathField value must be a list, got {type(value).__name__}: {repr(value)[:100]}')
        return super().get_prep_value(value)

    def from_db_value(self, value, expression, connection):
        """Convert JSON from database to Python list."""
        if value is None:
            return []
        # JSONField already deserializes JSON to Python
        return value if isinstance(value, list) else []

    def to_python(self, value):
        """Convert value to Python list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        # If it's a string (shouldn't happen), try to parse as JSON
        if isinstance(value, str):
            import json
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
        return []

# Register PathContains lookup for filtering
PathField.register_lookup(PathContains)
