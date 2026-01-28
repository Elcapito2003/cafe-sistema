from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    rol = db.Column(db.String(20), default='empleado')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Proveedor(db.Model):
    __tablename__ = 'proveedores'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    contacto = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    direccion = db.Column(db.String(200))
    banco = db.Column(db.String(50))
    num_cuenta = db.Column(db.String(30))
    clabe = db.Column(db.String(20))
    email = db.Column(db.String(100))
    whatsapp = db.Column(db.String(20))

    productos = db.relationship('ProductoProveedor', back_populates='proveedor')


class Producto(db.Model):
    __tablename__ = 'productos'

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), unique=True, nullable=False)
    unidad = db.Column(db.String(50))
    unidades_paquete = db.Column(db.Integer, default=1)
    contenido_unidad = db.Column(db.String(50))
    costo_actual = db.Column(db.Float, default=0)
    stock_actual = db.Column(db.Float, default=0)
    stock_minimo = db.Column(db.Float, default=0)

    proveedores = db.relationship('ProductoProveedor', back_populates='producto')
    movimientos = db.relationship('MovimientoInventario', back_populates='producto')


class ProductoProveedor(db.Model):
    __tablename__ = 'producto_proveedor'

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    proveedor_id = db.Column(db.Integer, db.ForeignKey('proveedores.id'), nullable=False)
    precio = db.Column(db.Float, default=0)
    tiempo_entrega = db.Column(db.Integer, default=1)

    producto = db.relationship('Producto', back_populates='proveedores')
    proveedor = db.relationship('Proveedor', back_populates='productos')

    __table_args__ = (db.UniqueConstraint('producto_id', 'proveedor_id'),)


class Compra(db.Model):
    __tablename__ = 'compras'

    id = db.Column(db.Integer, primary_key=True)
    producto = db.Column(db.String(100))
    proveedor = db.Column(db.String(100))
    tiempo_entrega = db.Column(db.String(10))
    cantidad = db.Column(db.Float)
    costo_unitario = db.Column(db.Float)
    iva_porcentaje = db.Column(db.Float)
    total_final = db.Column(db.Float)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.Column(db.String(80))


class MovimientoInventario(db.Model):
    __tablename__ = 'movimientos_inventario'

    id = db.Column(db.Integer, primary_key=True)
    producto_id = db.Column(db.Integer, db.ForeignKey('productos.id'), nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # entrada, salida, merma, ajuste
    cantidad = db.Column(db.Float, nullable=False)
    motivo = db.Column(db.String(200))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.Column(db.String(80))

    producto = db.relationship('Producto', back_populates='movimientos')
