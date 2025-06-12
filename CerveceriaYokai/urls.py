"""
URL configuration for CerveceriaYokai project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from Cerveza import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.mostrarIndex, name='index'),
    path('carrito/', views.mostrarCarrito, name='carrito'),
    path('carrito/sync/', views.sync_cart, name='sync_cart'),
    path('proceder-pago/', views.proceder_pago, name='proceder_pago'),
    path('pedido/<int:pedido_id>/', views.detalle_pedido, name='detalle_pedido'),
    path('carrito/clear/', views.clear_cart, name='clear_cart'),
    path('seguimiento/', views.seguimiento_pedido, name='seguimiento_pedido'),
    path('gestion-pedidos/', include([
        path('', views.lista_pedidos, name='lista_pedidos'),
        path('<int:pedido_id>/', views.detalle_pedido_admin, name='detalle_pedido_admin'),
        path('<int:pedido_id>/cambiar-estado/', views.cambiar_estado_pedido, name='cambiar_estado_pedido'),
    ])),
    path('cervezas/<int:cerveza_id>/resenas/', views.obtener_resenas, name='obtener_resenas'),
    path('cervezas/<int:cerveza_id>/resenas/agregar/', views.agregar_resena, name='agregar_resena'),
    path('historia-yokai/', views.historia_yokai, name='historia'),
    
    path('inventario/', include('Cerveza.urls')), 
    path('accounts/login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
