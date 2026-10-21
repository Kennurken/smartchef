from django.urls import path
from . import views
urlpatterns=[path("",views.index,name="index"),path("save/",views.save_recipe,name="save_recipe"),path("saved/",views.saved_recipes,name="saved_recipes"),path("cook/draft/",views.cooking,name="cook_draft"),path("cook/<int:recipe_id>/",views.cooking,name="cook_saved")]

from .editor import editor
urlpatterns += [path("edit/<int:recipe_id>/",editor,name="edit_recipe")]
