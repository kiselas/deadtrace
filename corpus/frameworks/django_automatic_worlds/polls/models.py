from django.db import models


class Question(models.Model):
    text = models.CharField(max_length=200)

    def was_published_recently(self) -> bool:
        return True


def unused_model_helper() -> None:
    pass
