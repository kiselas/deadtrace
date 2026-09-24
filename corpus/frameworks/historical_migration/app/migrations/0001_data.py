from typing import ClassVar

from django.db import migrations


def migration_helper() -> None:
    pass


def forwards(apps, schema_editor) -> None:
    del apps, schema_editor
    migration_helper()


class Migration(migrations.Migration):
    operations: ClassVar[list[object]] = [migrations.RunPython(forwards, migrations.RunPython.noop)]
