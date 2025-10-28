from django.db import models
from django.db.models import OuterRef, Subquery, Q, Value
from extras.models.tags import TaggedItem
from utilities.query_functions import EmptyGroupByJSONBAgg
from utilities.querysets import RestrictedQuerySet

__all__ = (
    'ConfigContextModelQuerySet',
    'ConfigContextQuerySet',
    'NotificationQuerySet',
)


class ConfigContextQuerySet(RestrictedQuerySet):

    def get_for_object(self, obj, aggregate_data=False):
        """
        Return all applicable ConfigContexts for a given object. Only active ConfigContexts will be included.

        Args:
          aggregate_data: If True, use the JSONBAgg aggregate function to return only the list of JSON data objects
        """

        # Device type and location assignment are relevant only for Devices
        device_type = getattr(obj, 'device_type', None)
        location = getattr(obj, 'location', None)
        locations = location.get_ancestors(include_self=True) if location else []

        # Get assigned cluster, group, and type (if any)
        cluster = getattr(obj, 'cluster', None)
        cluster_type = getattr(cluster, 'type', None)
        cluster_group = getattr(cluster, 'group', None)

        # Get the group of the assigned tenant, if any
        tenant_group = obj.tenant.group if obj.tenant else None

        # Match against the directly assigned region as well as any parent regions.
        region = getattr(obj.site, 'region', None)
        regions = region.get_ancestors(include_self=True) if region else []

        # Match against the directly assigned site group as well as any parent site groups.
        sitegroup = getattr(obj.site, 'group', None)
        sitegroups = sitegroup.get_ancestors(include_self=True) if sitegroup else []

        # Match against the directly assigned role as well as any parent roles.
        device_roles = obj.role.get_ancestors(include_self=True) if obj.role else []

        queryset = self.filter(
            Q(regions__in=regions) | Q(regions__isnull=True),
            Q(site_groups__in=sitegroups) | Q(site_groups__isnull=True),
            Q(sites=obj.site) | Q(sites__isnull=True),
            Q(locations__in=locations) | Q(locations__isnull=True),
            Q(device_types=device_type) | Q(device_types__isnull=True),
            Q(roles__in=device_roles) | Q(roles__isnull=True),
            Q(platforms=obj.platform) | Q(platforms__isnull=True),
            Q(cluster_types=cluster_type) | Q(cluster_types__isnull=True),
            Q(cluster_groups=cluster_group) | Q(cluster_groups__isnull=True),
            Q(clusters=cluster) | Q(clusters__isnull=True),
            Q(tenant_groups=tenant_group) | Q(tenant_groups__isnull=True),
            Q(tenants=obj.tenant) | Q(tenants__isnull=True),
            Q(tags__slug__in=obj.tags.slugs()) | Q(tags__isnull=True),
            is_active=True,
        ).order_by('weight', 'name').distinct()

        if aggregate_data:
            agg = queryset.aggregate(
                config_context_data=EmptyGroupByJSONBAgg('weight', 'name', 'data')
            )['config_context_data']
            if agg is None:
                return list(queryset.values_list('data', flat=True))
            return agg

        return queryset


class ConfigContextModelQuerySet(RestrictedQuerySet):
    """
    QuerySet manager used by models which support ConfigContext (device and virtual machine).

    Includes a method which appends an annotation of aggregated config context JSON data objects. This is
    implemented as a subquery which performs all the joins necessary to filter relevant config context objects.
    This offers a substantial performance gain over ConfigContextQuerySet.get_for_object() when dealing with
    multiple objects. This allows the annotation to be entirely optional.
    """
    def annotate_config_context_data(self):
        """
        Attach the subquery annotation to the base queryset.

        For SQLite compatibility: Returns empty array to force fallback to get_for_object().
        This is necessary because SQLite's .annotate().values() creates GROUP BY which
        prevents proper aggregation of all matching config contexts in a subquery.

        The get_config_context() method will detect the empty array and fall back to
        direct query via get_for_object(), ensuring correct data at the cost of N+1 queries.

        Note: .distinct() is applied to the main queryset to eliminate duplicates from many-to-many
        relationships (e.g., tags).
        """
        # Return empty array to trigger fallback in get_config_context()
        # This ensures correctness for SQLite at the cost of performance
        return self.annotate(
            config_context_data=Value('[]', output_field=models.JSONField())
        ).distinct()

class NotificationQuerySet(RestrictedQuerySet):

    def unread(self):
        """
        Return only unread notifications.
        """
        return self.filter(read__isnull=True)
