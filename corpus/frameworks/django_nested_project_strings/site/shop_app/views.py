from django.http import HttpResponse


def home(request):
    return HttpResponse("home")


def unused_view(request):
    return HttpResponse("never routed")
