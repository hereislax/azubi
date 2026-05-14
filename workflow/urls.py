from django.urls import path

from . import views

app_name = 'workflow'

urlpatterns = [
    path('einstellungen/',                 views.workflow_list,   name='list'),
    path('einstellungen/<slug:code>/',     views.workflow_edit,   name='edit'),
    path('einstellungen/<slug:code>/step/add/',
         views.step_add,    name='step_add'),
    path('einstellungen/step/<int:step_pk>/edit/',
         views.step_edit,   name='step_edit'),
    path('einstellungen/step/<int:step_pk>/delete/',
         views.step_delete, name='step_delete'),
    path('einstellungen/step/<int:step_pk>/move/<str:direction>/',
         views.step_move,   name='step_move'),
]
