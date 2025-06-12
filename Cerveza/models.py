from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
import uuid

class UsuarioManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('tipo_usuario', 'admin')
        return self.create_user(username, email, password, **extra_fields)

class Usuario(AbstractBaseUser, PermissionsMixin):
    CLIENTE = 'cliente'
    ADMIN = 'admin'
    STAFF = 'staff'

    TIPO_USUARIO_EL = [
        (CLIENTE, 'Cliente'),
        (ADMIN, 'Administrador'),
        (STAFF, 'Personal')
    ]

    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    tipo_usuario = models.CharField(max_length=10, choices=TIPO_USUARIO_EL, default=CLIENTE)
    direccion = models.TextField(blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Necesario para admin

    objects = UsuarioManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    def __str__(self):
        return self.username

    @property
    def is_superuser(self):
        return self.tipo_usuario == self.ADMIN

    @property
    def is_staff(self):
        return self.tipo_usuario in [self.ADMIN, self.STAFF]

class Cerveza(models.Model):
    ESTILOS = [
        ('PILSEN', 'Pilsen'),
        ('IPA', 'IPA'),
        ('AMBER ALE', 'Amber Ale'),
        ('BOCK', 'Bock'),
        ('OTRO', 'Otro')
    ]
    
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    estilo = models.CharField(max_length=10, choices=ESTILOS)
    alcohol = models.DecimalField(max_digits=3, decimal_places=1)
    precio = models.PositiveIntegerField()
    stock = models.PositiveIntegerField()
    imagen = models.ImageField(upload_to='cervezas/')
    yokai_asociado = models.CharField(max_length=100)
    historia_yokai = models.TextField()
    ingredientes = models.TextField()
    destacado = models.BooleanField(default=False)

class Pedido(models.Model):
    ESTADO_PEDIDO = [
        ('PENDIENTE', 'Pendiente'),
        ('PROCESANDO', 'Procesando'),
        ('ENVIADO', 'Enviado'),
        ('ENTREGADO', 'Entregado'),
        ('CANCELADO', 'Cancelado')
    ]
    
    METODO_PAGO = [
        ('TRANSFERENCIA', 'Transferencia Bancaria'),
        ('WEBPAY', 'WebPay'),
        ('EFECTIVO', 'Efectivo al Retirar')
    ]
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    nombre_cliente = models.CharField(max_length=100)  # Nuevo campo
    fecha_pedido = models.DateTimeField()
    estado = models.CharField(max_length=10, choices=ESTADO_PEDIDO, default='PENDIENTE')
    direccion_envio = models.TextField()
    telefono_contacto = models.CharField(max_length=20)
    total = models.PositiveIntegerField()
    metodo_pago = models.CharField(max_length=50, choices=METODO_PAGO)
    codigo_seguimiento = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.codigo_seguimiento:
            # Genera un código de 10 caracteres alfanuméricos
            self.codigo_seguimiento = uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Pedido #{self.id} - {self.nombre_cliente}"

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, related_name='items', on_delete=models.CASCADE)
    cerveza = models.ForeignKey(Cerveza, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario
    
class Carrito(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

class ItemCarrito(models.Model):
    carrito = models.ForeignKey(Carrito, related_name='items', on_delete=models.CASCADE)
    cerveza = models.ForeignKey(Cerveza, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)
    
    @property
    def subtotal(self):
        return self.cantidad * self.cerveza.precio
    
class Resena(models.Model):
    cerveza = models.ForeignKey(
        'Cerveza', 
        on_delete=models.CASCADE,
        related_name='resenas'
    )
    nombre = models.CharField(max_length=100)
    puntuacion = models.IntegerField(
        choices=[(1, '1 Estrella'), (2, '2 Estrellas'), 
                 (3, '3 Estrellas'), (4, '4 Estrellas'), 
                 (5, '5 Estrellas')]
    )
    comentario = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-fecha']  # Ordenar por fecha descendente por defecto
    
    def __str__(self):
        return f"Reseña de {self.nombre} para {self.cerveza.nombre}"

class MovimientoInventario(models.Model):
    TIPO_MOVIMIENTO = [
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
        ('AJUSTE', 'Ajuste')
    ]

    cerveza = models.ForeignKey(Cerveza, on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    tipo = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO)
    motivo = models.TextField()
    fecha = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.SET_NULL, null=True, blank=True)