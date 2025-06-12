from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Cerveza, MovimientoInventario, Pedido, DetallePedido, Resena
from .forms import CervezaForm, ResenaForm
from django.db.models import Q
import json
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime
import re
from django.http import JsonResponse

# Vista principal
def mostrarIndex(request):
    # Limpiar el carrito si venimos de completar un pedido
    if request.session.get('pedido_completado', False):
        if 'carrito' in request.session:
            del request.session['carrito']
        if 'subtotal' in request.session:
            del request.session['subtotal']
        if 'envio' in request.session:
            del request.session['envio']
        if 'total' in request.session:
            del request.session['total']
        del request.session['pedido_completado']
        request.session.modified = True
    
    # Obtener solo cervezas con stock > 0 y destacadas
    try:
        cervezas = Cerveza.objects.filter(destacado=True, stock__gt=0).exclude(imagen='')[:6]
    except Exception as e:
        print(f"Error al obtener cervezas: {e}")
        cervezas = []
    
    return render(request, 'index.html', {
        'cervezas': cervezas,
        'mostrar_alerta_reposicion': Cerveza.objects.filter(destacado=True, stock=0).exists()
    })

# Vista del carrito
def mostrarCarrito(request):
    # Obtener carrito desde localStorage (pasado por GET) o de la sesión
    cart_from_local_storage = request.GET.get('cart', '[]')
    
    try:
        cart_items = json.loads(cart_from_local_storage)
    except json.JSONDecodeError:
        cart_items = []
    
    # Sincronizar con el carrito de sesión de Django
    if 'carrito' not in request.session:
        request.session['carrito'] = []
    
    # Procesar items y calcular totales
    cervezas_en_carrito = []
    subtotal = 0
    carrito_actualizado = []
    
    for item in cart_items:
        try:
            cerveza = Cerveza.objects.get(id=item['id'])
            cantidad = min(item.get('quantity', 1), cerveza.stock)
            precio = float(cerveza.precio)
            item_total = precio * cantidad
            
            # Actualizar datos para sesión Django
            carrito_actualizado.append({
                'id': item['id'],
                'cantidad': cantidad,
                'max_stock': cerveza.stock  # Esto viene directo de la BD
            })
            
            # Datos para template
            cervezas_en_carrito.append({
                'id': cerveza.id,
                'nombre': cerveza.nombre,
                'imagen': cerveza.imagen.url if cerveza.imagen else '',
                'precio': precio,
                'cantidad': cantidad,
                'total_item': item_total,
                'stock': cerveza.stock  # Valor directo de la BD
            })
            
            subtotal += item_total
            
        except Cerveza.DoesNotExist:
            continue
    
    # Actualizar valores en sesión
    envio = 0 if subtotal > 10000 else 3000
    total = subtotal + envio
    
    request.session['carrito'] = carrito_actualizado
    request.session['subtotal'] = float(subtotal)
    request.session['envio'] = float(envio)
    request.session['total'] = float(total)
    request.session.modified = True
    
    context = {
        'cervezas': cervezas_en_carrito,
        'subtotal': subtotal,
        'envio': envio,
        'total': total,
        'cart_json': json.dumps([{
            'id': item['id'],
            'name': item['nombre'],
            'image': item['imagen'],
            'price': item['precio'],
            'quantity': item['cantidad'],
            'max_stock': item['stock']  # Cambiado de max_stock a stock (valor de BD)
        } for item in cervezas_en_carrito])
    }
    
    return render(request, 'carrito.html', context)

# Sincronización del carrito con AJAX
@csrf_exempt
def sync_cart(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            cart_items = data.get('cart', [])
            
            valid_items = []
            for item in cart_items:
                try:
                    cerveza = Cerveza.objects.get(id=item['id'])
                    cantidad = min(item.get('quantity', 1), cerveza.stock)
                    
                    if cantidad > 0:  # Solo agregar items válidos
                        valid_items.append({
                            'id': item['id'],
                            'cantidad': cantidad
                        })
                except (Cerveza.DoesNotExist, KeyError):
                    continue  # Omitir items inválidos
            
            # Actualizar carrito en la sesión
            request.session['carrito'] = valid_items
            request.session.modified = True
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error'}, status=405)

@csrf_exempt
def clear_cart(request):
    if request.method == 'POST':
        for key in ['carrito', 'subtotal', 'envio', 'total']:
            if key in request.session:
                del request.session[key]
        request.session.modified = True
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)
# Proceso de pago
def proceder_pago(request):
    # Verificar si hay carrito en la sesión
    if 'carrito' not in request.session or not request.session['carrito']:
        messages.warning(request, 'Tu carrito está vacío')
        return redirect('carrito')
    
    # Obtener valores de la sesión
    subtotal = request.session.get('subtotal', 0)
    envio = request.session.get('envio', 3000)
    total = request.session.get('total', 0)

    if request.method == 'POST':
        try:
            # Validar datos del formulario
            nombre_cliente = request.POST.get('nombre_cliente', '').strip()
            direccion_envio = request.POST.get('direccion_envio', '').strip()
            telefono_contacto = request.POST.get('telefono_contacto', '').strip()
            metodo_pago = request.POST.get('metodo_pago')
            fecha_cliente_str = request.POST.get('fecha_cliente')
            
            try:
                fecha_cliente = datetime.strptime(fecha_cliente_str, '%Y-%m-%d %H:%M:%S')
                # Asumir que la fecha del cliente ya está en la zona horaria correcta
                fecha_cliente_aware = timezone.make_aware(fecha_cliente)
            except (ValueError, TypeError) as e:
                print(f"Error al parsear fecha del cliente: {e}")
                fecha_cliente_aware = timezone.now()

            # Validaciones básicas
            if not all([nombre_cliente, direccion_envio, telefono_contacto, metodo_pago]):
                messages.error(request, 'Todos los campos son obligatorios')
                return redirect('proceder_pago')

            # Convertir la fecha del cliente a datetime

            # Crear el pedido con los valores de la sesión
            pedido = Pedido.objects.create(
                usuario=request.user if request.user.is_authenticated else None,
                nombre_cliente=nombre_cliente,
                direccion_envio=direccion_envio,
                telefono_contacto=telefono_contacto,
                total=total,
                metodo_pago=metodo_pago,
                estado='PENDIENTE',
                fecha_pedido=fecha_cliente_aware  # Usamos la fecha del cliente
            )

            # Resto del código para crear detalles del pedido...
            for item in request.session['carrito']:
                cerveza = Cerveza.objects.get(id=item['id'])
                DetallePedido.objects.create(
                    pedido=pedido,
                    cerveza=cerveza,
                    cantidad=item['cantidad'],
                    precio_unitario=cerveza.precio
                )
                # Actualizar stock
                cerveza.stock -= item['cantidad']
                cerveza.save()

            # Limpiar carrito
            for key in ['carrito', 'subtotal', 'envio', 'total']:
                if key in request.session:
                    del request.session[key]
            request.session.modified = True

            return redirect('detalle_pedido', pedido_id=pedido.id)

        except Exception as e:
            messages.error(request, f'Error al procesar el pedido: {str(e)}')
            return redirect('proceder_pago')

    # Mostrar formulario con los valores correctos
    context = {
        'subtotal': subtotal,
        'envio': envio,
        'total': total
    }
    return render(request, 'pago/proceder_pago.html', context)

# Detalle del pedido completado
def detalle_pedido(request, pedido_id):
    try:
        pedido = Pedido.objects.get(id=pedido_id)
        items = DetallePedido.objects.filter(pedido=pedido)
        
        # Limpiar carrito
        if 'carrito' in request.session:
            del request.session['carrito']
        if 'subtotal' in request.session:
            del request.session['subtotal']
        if 'envio' in request.session:
            del request.session['envio']
        if 'total' in request.session:
            del request.session['total']
        
        request.session.modified = True
        
        return render(request, 'pago/detalle_pedido.html', {
            'pedido': pedido,
            'items': items,
            'subtotal': pedido.total - (0 if pedido.total > 50000 else 3000),
            'envio': 0 if pedido.total > 50000 else 3000
        })
    except Pedido.DoesNotExist:
        messages.error(request, 'Pedido no encontrado')
        return redirect('index')

# Funciones de administración (inventario)
def is_staff(user):
    return user.is_authenticated and user.tipo_usuario in ['admin', 'staff']

@login_required
@user_passes_test(is_staff)
def lista_inventario(request):
    query = request.GET.get('q', '')
    filter_type = request.GET.get('filter', 'all')
    
    cervezas = Cerveza.objects.all()
    
    if query:
        cervezas = cervezas.filter(
            Q(nombre__icontains=query) |
            Q(descripcion__icontains=query) |
            Q(yokai_asociado__icontains=query)
        )
    
    if filter_type == 'featured':
        cervezas = cervezas.filter(destacado=True)
    elif filter_type == 'low':
        cervezas = cervezas.filter(stock__lt=10)
    
    return render(request, 'inventario/lista.html', {
        'cervezas': cervezas,
        'filter': filter_type
    })

@login_required
@user_passes_test(is_staff)
def agregar_cerveza(request):
    if request.method == 'POST':
        form = CervezaForm(request.POST, request.FILES)
        if form.is_valid():
            cerveza = form.save()
            MovimientoInventario.objects.create(
                cerveza=cerveza,
                cantidad=cerveza.stock,
                tipo='ENTRADA',
                motivo='Entrada inicial de inventario',
                usuario=request.user
            )
            messages.success(request, 'Cerveza agregada correctamente!')
            return redirect('inventario:lista')
    else:
        form = CervezaForm()
    return render(request, 'inventario/agregar.html', {'form': form})

@login_required
@user_passes_test(is_staff)
def editar_cerveza(request, id):
    cerveza = get_object_or_404(Cerveza, id=id)
    if request.method == 'POST':
        form = CervezaForm(request.POST, request.FILES, instance=cerveza)
        if form.is_valid():
            if 'stock' not in form.cleaned_data or not form.cleaned_data['stock']:
                form.instance.stock = cerveza.stock
            form.save()
            messages.success(request, 'Cerveza actualizada correctamente!')
            return redirect('inventario:lista')
    else:
        form = CervezaForm(instance=cerveza)
    
    return render(request, 'inventario/editar.html', {'form': form, 'cerveza': cerveza})

@login_required
@user_passes_test(is_staff)
def eliminar_cerveza(request, id):
    cerveza = get_object_or_404(Cerveza, id=id)
    if request.method == 'POST':
        cerveza.delete()
        messages.success(request, 'Cerveza eliminada correctamente!')
        return redirect('inventario:lista')
    return render(request, 'inventario/eliminar.html', {'cerveza': cerveza})

@login_required
@user_passes_test(is_staff)
def ajustar_inventario(request, id):
    cerveza = get_object_or_404(Cerveza, id=id)
    if request.method == 'POST':
        cantidad = int(request.POST.get('cantidad'))
        motivo = request.POST.get('motivo')
        tipo = request.POST.get('tipo')
        
        if tipo == 'ENTRADA':
            cerveza.stock += cantidad
        elif tipo == 'SALIDA':
            cerveza.stock -= cantidad
        elif tipo == 'AJUSTE':
            cerveza.stock = cantidad
        
        cerveza.save()
        
        MovimientoInventario.objects.create(
            cerveza=cerveza,
            cantidad=cantidad,
            tipo=tipo,
            motivo=motivo,
            usuario=request.user
        )
        
        messages.success(request, f'Inventario de {cerveza.nombre} ajustado correctamente!')
        return redirect('inventario:lista')
    
    return render(request, 'inventario/ajustar.html', {'cerveza': cerveza})

@login_required
@user_passes_test(is_staff)
def historial_inventario(request):
    movimientos = MovimientoInventario.objects.all().order_by('-fecha')
    return render(request, 'inventario/historial.html', {'movimientos': movimientos})

@csrf_exempt
def clear_cart(request):
    if request.method == 'POST':
        # Limpiar sesión
        for key in ['carrito', 'subtotal', 'envio', 'total']:
            if key in request.session:
                del request.session[key]
        request.session.modified = True
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

def seguimiento_pedido(request):
    codigo = request.GET.get('codigo', '').strip().upper()
    pedido = None
    detalles = None
    
    if codigo:
        try:
            pedido = Pedido.objects.get(codigo_seguimiento=codigo)
            detalles = DetallePedido.objects.filter(pedido=pedido)
            
            # Calcular progreso basado en el estado
            estados = ['PENDIENTE', 'PROCESANDO', 'ENVIADO', 'ENTREGADO']
            try:
                progreso = (estados.index(pedido.estado) + 1) / len(estados) * 100
            except ValueError:
                progreso = 25  # Valor por defecto si el estado no está en la lista
            
        except Pedido.DoesNotExist:
            messages.error(request, 'No se encontró un pedido con ese código de seguimiento')
    
    context = {
        'pedido': pedido,
        'detalles': detalles,
        'codigo': codigo,
        'progreso': int(progreso) if pedido else 0,
        'estados': {
            'PENDIENTE': 'Pedido recibido',
            'PROCESANDO': 'En preparación',
            'ENVIADO': 'En camino',
            'ENTREGADO': 'Entregado',
            'CANCELADO': 'Cancelado'
        }
    }
    
    return render(request, 'seguimiento.html', context)

@login_required
@user_passes_test(is_staff)
def lista_pedidos(request):
    # Filtros
    estado = request.GET.get('estado', '')
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    codigo = request.GET.get('codigo', '').strip().upper()
    
    pedidos = Pedido.objects.all().order_by('-fecha_pedido')
    
    # Aplicar filtros
    if estado:
        pedidos = pedidos.filter(estado=estado)
    if codigo:
        pedidos = pedidos.filter(codigo_seguimiento=codigo)
    if fecha_inicio:
        try:
            fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
            pedidos = pedidos.filter(fecha_pedido__gte=fecha_inicio)
        except ValueError:
            pass
    if fecha_fin:
        try:
            fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
            pedidos = pedidos.filter(fecha_pedido__lte=fecha_fin)
        except ValueError:
            pass
    
    context = {
        'pedidos': pedidos,
        'estados_pedido': Pedido.ESTADO_PEDIDO,
        'filtro_estado': estado,
        'filtro_codigo': codigo,
        'filtro_fecha_inicio': fecha_inicio,
        'filtro_fecha_fin': fecha_fin,
    }
    return render(request, 'admin_pedidos/lista_pedidos.html', context)

@login_required
@user_passes_test(is_staff)
def detalle_pedido_admin(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    detalles = DetallePedido.objects.filter(pedido=pedido)
    
    context = {
        'pedido': pedido,
        'detalles': detalles,
        'estados_pedido': Pedido.ESTADO_PEDIDO,
    }
    return render(request, 'admin_pedidos/detalle_pedido.html', context)

@login_required
@user_passes_test(is_staff)
@csrf_exempt
def cambiar_estado_pedido(request, pedido_id):
    pedido = get_object_or_404(Pedido, id=pedido_id)
    
    if request.method == 'POST':
        nuevo_estado = request.POST.get('nuevo_estado')
        
        if nuevo_estado in dict(Pedido.ESTADO_PEDIDO):
            pedido.estado = nuevo_estado
            pedido.save()
            
            # Si es una solicitud AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'nuevo_estado': pedido.get_estado_display(),
                    'nuevo_estado_raw': pedido.estado
                })
            
            messages.success(request, f'Estado del pedido #{pedido.id} actualizado a {pedido.get_estado_display()}')
            return redirect('detalle_pedido_admin', pedido_id=pedido.id)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'error', 'message': 'Estado inválido'}, status=400)
        
        messages.error(request, 'Estado inválido')
    
    return redirect('detalle_pedido_admin', pedido_id=pedido.id)


@require_http_methods(["GET"])
@require_http_methods(["GET"])
def obtener_resenas(request, cerveza_id):
    try:
        # Verificar si la cerveza existe
        cerveza = Cerveza.objects.get(id=cerveza_id)
        
        # Obtener reseñas ordenadas por fecha (más recientes primero)
        resenas = Resena.objects.filter(cerveza=cerveza).order_by('-fecha')
        
        # Preparar datos para la respuesta
        resenas_data = []
        total_puntuacion = 0
        
        for resena in resenas:
            resenas_data.append({
                'nombre': resena.nombre,
                'puntuacion': resena.puntuacion,
                'comentario': resena.comentario or '',  # Manejar None
                'fecha': resena.fecha.strftime('%Y-%m-%d %H:%M:%S')
            })
            total_puntuacion += resena.puntuacion
        
        # Calcular promedio (evitar división por cero)
        promedio = round(total_puntuacion / len(resenas), 1) if resenas else 0
        
        return JsonResponse({
            'success': True,
            'resenas': resenas_data,
            'promedio': float(promedio),  # Asegurar que es float
            'total_resenas': len(resenas)
        })
        
    except ObjectDoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'La cerveza solicitada no existe'
        }, status=404)
        
    except Exception as e:
        # Registrar el error para depuración
        print(f"Error al obtener reseñas: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Error interno al procesar la solicitud',
            'debug': str(e) if DEBUG else None
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def agregar_resena(request, cerveza_id):
    try:
        cerveza = Cerveza.objects.get(id=cerveza_id)
        
        nombre = request.POST.get('nombre')
        puntuacion = int(request.POST.get('puntuacion'))
        comentario = request.POST.get('comentario', '')
        
        if not nombre or not puntuacion:
            return JsonResponse({
                'success': False,
                'error': 'Nombre y puntuación son requeridos'
            }, status=400)
        
        if puntuacion < 1 or puntuacion > 5:
            return JsonResponse({
                'success': False,
                'error': 'La puntuación debe estar entre 1 y 5'
            }, status=400)
        
        nueva_resena = Resena(
            cerveza=cerveza,
            nombre=nombre,
            puntuacion=puntuacion,
            comentario=comentario,
            fecha=datetime.now()
        )
        nueva_resena.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Reseña agregada exitosamente'
        })
    except Cerveza.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Cerveza no encontrada'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def historia_yokai(request):
    # Puedes agregar lógica aquí si necesitas datos dinámicos
    # Por ejemplo, podrías obtener información de la base de datos
    
    context = {
        'page_title': 'Historia Yokai',
        'active_nav': 'historia',  # Para resaltar en el navbar
    }
    
    return render(request, 'historiayokai.html', context)
