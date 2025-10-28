from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('vpn', '0004_alter_ikepolicy_mode'),
    ]

    operations = [
        # Rename vpn_l2vpn constraints
        # Constraint rename (no-op on SQLite)
        migrations.RunPython(code=migrations.RunPython.noop),
        # Rename ipam_l2vpn_* sequences
        # Sequence renames (no-op on SQLite)
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        # Rename ipam_l2vpn_* indexes
        # Index renames (no-op on SQLite)
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        # Rename vpn_l2vpntermination constraints
        # Constraint renames (no-op on SQLite)
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        # Rename ipam_l2vpn_termination_* sequences
        # Sequence/index renames (no-op on SQLite)
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
        migrations.RunPython(code=migrations.RunPython.noop),
    ]
