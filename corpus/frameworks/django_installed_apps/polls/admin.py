from django.contrib import admin

from polls.models import Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request)
