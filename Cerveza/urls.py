from django.urls import path
from . import views

app_name = 'inventario'

urlpatterns = [
    path('', views.lista_inventario, name='lista'),
    path('agregar/', views.agregar_cerveza, name='agregar'),
    path('editar/<int:id>/', views.editar_cerveza, name='editar'),
    path('eliminar/<int:id>/', views.eliminar_cerveza, name='eliminar'),
    path('ajustar/<int:id>/', views.ajustar_inventario, name='ajustar'),
    path('historial/', views.historial_inventario, name='historial'),
    
]