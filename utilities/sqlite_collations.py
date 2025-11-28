"""SQLite collations and custom functions for NetBox.

Provides:
- Collations: 'C' (binary), 'natural_sort' (alphanumeric)
- IP/CIDR functions: INET_CONTAINS, INET_HOST, etc.
- JSON functions: RANGE_ARRAY_CONTAINS, ARRAY_CONTAINS, etc.
"""

import json
import re

from django.db.backends.signals import connection_created
from netaddr import IPNetwork, IPAddress

# Compile regex once at module level for performance
_NATURAL_SORT_CHUNK_RE = re.compile(r'(\d+|\D+)')


def _collate_c(a, b):
    """Binary collation (C locale)."""
    return (a > b) - (a < b)


def _natkey(s):
    """Generate natural sort key from string."""
    parts = _NATURAL_SORT_CHUNK_RE.findall(s or '')
    return [(0, int(p)) if p.isdigit() else (1, p.lower()) for p in parts]


def _collate_natural(a, b):
    """Natural sort collation (alphanumeric)."""
    ka, kb = _natkey(a), _natkey(b)
    return (ka > kb) - (ka < kb)


# SQLite UDF implementations
def _inet_contains(parent, child):
    """Check if parent network strictly contains child network."""
    try:
        p = IPNetwork(parent)
        c = IPNetwork(child)
        return int((c in p) and (c != p))
    except Exception:
        return 0


def _inet_contains_or_equals(parent, child):
    """Check if parent network contains or equals child network."""
    try:
        p = IPNetwork(parent)
        c = IPNetwork(child)
        return int((c in p) or (c == p))
    except Exception:
        return 0


def _inet_contained(child, parent):
    """Check if child network is strictly contained in parent network."""
    try:
        c = IPNetwork(child)
        p = IPNetwork(parent)
        return int((c in p) and (c != p))
    except Exception:
        return 0


def _inet_host(address):
    """Extract host address from CIDR notation."""
    try:
        return str(IPAddress(str(address).split('/')[0]))
    except Exception:
        return None


def _inet_cast(value):
    """Return a lexicographically sortable key for IP address strings.

    For IPv4: '4:' + zero-padded 3-digit octets (e.g., 192.168.0.1 -> '4:192168000001')
    For IPv6: '6:' + 32 hex digits (no colons), uppercase (e.g., full expanded form)
    Accepts inputs with or without mask; mask is ignored for comparison key.
    """
    try:
        s = str(value) if value is not None else ''
        host = s.split('/')[0]
        ip = IPAddress(host)
        if ip.version == 4:
            parts = [f"{int(o):03d}" for o in str(ip).split('.')]
            return '4:' + ''.join(parts)
        else:
            hexdigits = format(ip, 'x').replace(':', '').zfill(32)
            return '6:' + hexdigits.upper()
    except Exception:
        return None


def _family(address):
    """Return IP address family (4 or 6)."""
    try:
        ip = IPAddress(str(address).split('/')[0])
        return int(ip.version)
    except Exception:
        return None


def _masklen(address):
    """Return network mask length."""
    try:
        s = str(address)
        if '/' in s:
            return int(IPNetwork(s).prefixlen)
        ip = IPAddress(s)
        return 32 if ip.version == 4 else 128
    except Exception:
        return None


def _regexp(pattern, value):
    """SQLite REGEXP operator implementation."""
    try:
        return 1 if re.search(pattern, value or '') else 0
    except Exception:
        return 0


def _range_array_contains(json_array, scalar):
    """Check if scalar is contained in any range from JSON array."""
    try:
        ranges = json.loads(json_array) if isinstance(json_array, str) else json_array
    except Exception:
        return 0
    
    try:
        v = int(scalar)
    except Exception:
        return 0
    
    if not ranges:
        return 0
    
    for r in ranges:
        try:
            lower = int(r.get('lower'))
            upper = int(r.get('upper'))
            bounds = str(r.get('bounds', '[)'))
            lower_inc = bounds.startswith('[')
            upper_inc = bounds.endswith(']')
            lower_ok = (v >= lower) if lower_inc else (v > lower)
            upper_ok = (v <= upper) if upper_inc else (v < upper)
            if lower_ok and upper_ok:
                return 1
        except Exception:
            continue
    return 0


def _array_contains(json_array, scalar):
    """Check if JSON array contains scalar value."""
    try:
        arr = json.loads(json_array) if isinstance(json_array, str) else json_array
    except Exception:
        return 0
    
    try:
        v = int(scalar)
    except Exception:
        v = scalar
    
    try:
        return 1 if v in arr else 0
    except Exception:
        return 0


def _choices_contains_value(json_array, scalar):
    """Check if JSON choice array contains value."""
    try:
        arr = json.loads(json_array) if isinstance(json_array, str) else json_array
    except Exception:
        return 0
    
    try:
        for item in arr or []:
            # Flat scalar lists: ['A','B',...]
            if not isinstance(item, (list, tuple, dict)):
                if item == scalar:
                    return 1
                continue
            # [value, label] pairs
            if isinstance(item, (list, tuple)) and item:
                if item[0] == scalar:
                    return 1
                continue
            # {'value': ..., 'label': ...} dicts
            if isinstance(item, dict) and 'value' in item and item.get('value') == scalar:
                return 1
        return 0
    except Exception:
        return 0


def _date_cmp(a, b):
    """Lexicographic date comparison for ISO dates."""
    try:
        if a is None or b is None:
            return None
        sa = str(a)
        sb = str(b)
        if sa > sb:
            return 1
        if sa < sb:
            return -1
        return 0
    except Exception:
        return None


def _register_on_connection(conn):
    """Register SQLite collations and custom functions."""
    # Get the raw SQLite connection from Django's DatabaseWrapper
    raw_conn = conn.connection
    
    # Register collations
    try:
        raw_conn.create_collation('C', _collate_c)
    except AttributeError:
        pass  # Not a SQLite connection
    
    try:
        raw_conn.create_collation('natural_sort', _collate_natural)
    except AttributeError:
        pass  # Not a SQLite connection
    
    # Register IP/CIDR functions
    try:
        raw_conn.create_function('INET_CONTAINS', 2, _inet_contains)
        raw_conn.create_function('INET_CONTAINS_OR_EQUALS', 2, _inet_contains_or_equals)
        raw_conn.create_function('INET_CONTAINED', 2, _inet_contained)
        raw_conn.create_function('INET_HOST', 1, _inet_host)
        raw_conn.create_function('HOST', 1, _inet_host)  # Alias for transforms
        raw_conn.create_function('INET', 1, _inet_cast)
        raw_conn.create_function('FAMILY', 1, _family)
        raw_conn.create_function('MASKLEN', 1, _masklen)
        raw_conn.create_function('REGEXP', 2, _regexp)
        raw_conn.create_function('regexp', 2, _regexp)
        raw_conn.create_function('RANGE_ARRAY_CONTAINS', 2, _range_array_contains)
        raw_conn.create_function('ARRAY_CONTAINS', 2, _array_contains)
        raw_conn.create_function('CHOICES_CONTAINS_VALUE', 2, _choices_contains_value)
        raw_conn.create_function('DATE_CMP', 2, _date_cmp)
    except AttributeError:
        pass  # Not a SQLite connection

def _on_created(sender, connection, **kwargs):
    _register_on_connection(connection)

# Connect signal to register collations for future SQLite connections
connection_created.connect(_on_created)
