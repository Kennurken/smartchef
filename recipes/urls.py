from django.urls import path
from . import views
urlpatterns=[path("",views.index,name="index"),path("save/",views.save_recipe,name="save_recipe"),path("saved/",views.saved_recipes,name="saved_recipes")]
