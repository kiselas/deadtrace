from django.db import models


class Vimeo(models.Model):
    url = models.URLField()


def _helper():
    return None
