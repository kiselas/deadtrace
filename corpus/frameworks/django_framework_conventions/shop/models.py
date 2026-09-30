from typing import ClassVar

from django.db import models


class Product(models.Model):
    name = models.CharField(max_length=100)

    class Meta:
        ordering: ClassVar[list[str]] = ["name"]


class PlainHelper:
    """A class with no base is no model, whatever module it stands in."""

    def total(self) -> int:
        return 0
