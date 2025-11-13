from dcim.utils import object_to_path_node
from django.db import connection
from django.db.models import Lookup

class PathContains(Lookup):
    lookup_name = 'path_contains'

    def as_sql(self, compiler, connection):
        raise TypeError('PathContains lookup is not supported')


