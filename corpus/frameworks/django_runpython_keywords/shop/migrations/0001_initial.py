from typing import ClassVar

from django.db import migrations


def forwards(apps: object, schema_editor: object) -> None:
    pass


def backwards(apps: object, schema_editor: object) -> None:
    pass


class Migration(migrations.Migration):
    operations: ClassVar[list[object]] = [
        migrations.RunPython(code=forwards, reverse_code=migrations.RunPython.noop),
        migrations.RunPython(forwards, reverse_code=backwards),
    ]
