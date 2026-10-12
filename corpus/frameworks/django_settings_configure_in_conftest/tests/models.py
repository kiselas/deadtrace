from django.db import models


class Anchor(models.Model):
    name = models.CharField(max_length=10)


def _helper():
    return None
