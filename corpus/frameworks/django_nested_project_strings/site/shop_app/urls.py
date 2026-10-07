from django.urls import path

from shop_app.views import home

urlpatterns = [path("", home)]
