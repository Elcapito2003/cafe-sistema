from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from config import Config
from models import db, Usuario, Proveedor, Producto, ProductoProveedor, Compra
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor inicia sesion para acceder.'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Crear tablas y admin por defecto
with app.app_context():
    db.create_all()
    if not Usuario.query.filter_by(username='admin').first():
        admin = Usuario(username='admin', rol='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()

# --- RUTAS DE AUTENTICACION ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = Usuario.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Bienvenido!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuario o contrasena incorrectos', 'error')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sesion cerrada', 'info')
    return redirect(url_for('login'))

# --- DASHBOARD ---
@app.route('/dashboard')
@login_required
def dashboard():
    total_productos = Producto.query.count()
    total_proveedores = Proveedor.query.count()
    total_compras = Compra.query.count()

    ultimas_compras = Compra.query.order_by(Compra.id.desc()).limit(5).all()

    return render_template('dashboard.html',
                         total_productos=total_productos,
                         total_proveedores=total_proveedores,
                         total_compras=total_compras,
                         ultimas_compras=ultimas_compras)

# --- COMPRAS ---
@app.route('/compras', methods=['GET', 'POST'])
@login_required
def compras():
    if request.method == 'POST':
        producto_id = request.form.get('producto_id')
        proveedor_nombre = request.form.get('proveedor')
        cantidad = float(request.form.get('cantidad', 0))
        costo = float(request.form.get('costo', 0))
        iva = float(request.form.get('iva', 16))
        tiempo = request.form.get('tiempo_entrega', '1')

        producto = Producto.query.get(producto_id)
        if producto and cantidad > 0 and costo > 0:
            subtotal = cantidad * costo
            total = subtotal * (1 + iva/100)

            compra = Compra(
                producto=producto.nombre,
                proveedor=proveedor_nombre,
                tiempo_entrega=tiempo,
                cantidad=cantidad,
                costo_unitario=costo,
                iva_porcentaje=iva,
                total_final=total,
                usuario=current_user.username
            )
            db.session.add(compra)

            # Actualizar costo actual del producto
            producto.costo_actual = costo
            db.session.commit()

            flash(f'Compra registrada: ${total:,.2f}', 'success')
        else:
            flash('Verifica los datos ingresados', 'error')

        return redirect(url_for('compras'))

    productos = Producto.query.all()
    return render_template('compras.html', productos=productos)

@app.route('/api/producto/<int:producto_id>/proveedores')
@login_required
def get_proveedores_producto(producto_id):
    """API para obtener proveedores de un producto"""
    relaciones = ProductoProveedor.query.filter_by(producto_id=producto_id).all()
    proveedores = []
    for rel in relaciones:
        proveedores.append({
            'id': rel.proveedor.id,
            'nombre': rel.proveedor.nombre,
            'precio': rel.precio,
            'tiempo_entrega': rel.tiempo_entrega
        })
    return jsonify(proveedores)

# --- PRODUCTOS ---
@app.route('/productos', methods=['GET', 'POST'])
@login_required
def productos():
    if current_user.rol != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'crear_producto':
            nombre = request.form.get('nombre')
            unidad = request.form.get('unidad')
            unidades_paq = request.form.get('unidades_paquete', 1)
            contenido = request.form.get('contenido_unidad', '')

            if nombre and unidad:
                if Producto.query.filter_by(nombre=nombre).first():
                    flash('Este producto ya existe', 'error')
                else:
                    producto = Producto(
                        nombre=nombre,
                        unidad=unidad,
                        unidades_paquete=int(unidades_paq) if unidades_paq else 1,
                        contenido_unidad=contenido
                    )
                    db.session.add(producto)
                    db.session.commit()
                    flash(f'Producto "{nombre}" creado', 'success')
            else:
                flash('Nombre y unidad son obligatorios', 'error')

        elif action == 'asignar_proveedor':
            producto_id = request.form.get('producto_id')
            proveedor_id = request.form.get('proveedor_id')
            precio = request.form.get('precio', 0)
            tiempo = request.form.get('tiempo_entrega', 1)

            if producto_id and proveedor_id and precio:
                # Verificar si ya existe la relacion
                existente = ProductoProveedor.query.filter_by(
                    producto_id=producto_id, proveedor_id=proveedor_id
                ).first()

                if existente:
                    existente.precio = float(precio)
                    existente.tiempo_entrega = int(tiempo) if tiempo else 1
                else:
                    rel = ProductoProveedor(
                        producto_id=int(producto_id),
                        proveedor_id=int(proveedor_id),
                        precio=float(precio),
                        tiempo_entrega=int(tiempo) if tiempo else 1
                    )
                    db.session.add(rel)

                db.session.commit()
                flash('Proveedor asignado correctamente', 'success')
            else:
                flash('Faltan datos para asignar proveedor', 'error')

        return redirect(url_for('productos'))

    productos_list = Producto.query.all()
    proveedores_list = Proveedor.query.all()

    # Obtener info de proveedores por producto
    productos_info = []
    for p in productos_list:
        provs = ProductoProveedor.query.filter_by(producto_id=p.id).all()
        provs_str = ", ".join([f"{r.proveedor.nombre} (${r.precio:.0f})" for r in provs]) or "Sin proveedores"
        mejor_precio = min([r.precio for r in provs]) if provs else 0
        productos_info.append({
            'producto': p,
            'proveedores_str': provs_str,
            'mejor_precio': mejor_precio
        })

    return render_template('productos.html',
                         productos_info=productos_info,
                         proveedores=proveedores_list)

# --- PROVEEDORES ---
@app.route('/proveedores', methods=['GET', 'POST'])
@login_required
def proveedores():
    if current_user.rol != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        contacto = request.form.get('contacto', '')
        telefono = request.form.get('telefono', '')
        direccion = request.form.get('direccion', '')
        banco = request.form.get('banco', '')
        num_cuenta = request.form.get('num_cuenta', '')
        clabe = request.form.get('clabe', '')
        email = request.form.get('email', '')
        whatsapp = request.form.get('whatsapp', '')

        if nombre:
            if Proveedor.query.filter_by(nombre=nombre).first():
                flash('Este proveedor ya existe', 'error')
            else:
                proveedor = Proveedor(
                    nombre=nombre,
                    contacto=contacto,
                    telefono=telefono,
                    direccion=direccion,
                    banco=banco,
                    num_cuenta=num_cuenta,
                    clabe=clabe,
                    email=email,
                    whatsapp=whatsapp
                )
                db.session.add(proveedor)
                db.session.commit()
                flash(f'Proveedor "{nombre}" agregado', 'success')
        else:
            flash('El nombre es obligatorio', 'error')

        return redirect(url_for('proveedores'))

    proveedores_list = Proveedor.query.all()
    return render_template('proveedores.html', proveedores=proveedores_list)

@app.route('/proveedores/eliminar/<int:id>')
@login_required
def eliminar_proveedor(id):
    if current_user.rol != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))

    proveedor = Proveedor.query.get_or_404(id)
    ProductoProveedor.query.filter_by(proveedor_id=id).delete()
    db.session.delete(proveedor)
    db.session.commit()
    flash(f'Proveedor "{proveedor.nombre}" eliminado', 'success')
    return redirect(url_for('proveedores'))

# --- ORDENES DE COMPRA ---
@app.route('/ordenes')
@login_required
def ordenes():
    productos = Producto.query.all()
    return render_template('ordenes.html', productos=productos)

@app.route('/api/enviar-orden', methods=['POST'])
@login_required
def enviar_orden():
    """API para enviar orden por email"""
    data = request.json
    items = data.get('items', [])
    email_from = data.get('email_from')
    email_pass = data.get('email_pass')
    enviar_a_proveedores = data.get('enviar_a_proveedores', False)

    if not items:
        return jsonify({'success': False, 'message': 'No hay items en la orden'})

    # Agrupar por proveedor
    por_proveedor = {}
    for item in items:
        prov = item['proveedor']
        if prov not in por_proveedor:
            por_proveedor[prov] = []
        por_proveedor[prov].append(item)

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M")
    enviados = []
    errores = []

    for prov_nombre, items_prov in por_proveedor.items():
        total_prov = sum(float(i['cantidad']) * float(i['precio']) for i in items_prov)

        mensaje = f"PEDIDO - Cafeteria\nFecha: {fecha}\n\n"
        mensaje += "Productos solicitados:\n\n"
        for item in items_prov:
            mensaje += f"- {item['producto']}: {item['cantidad']} unidades\n"
        mensaje += f"\nTotal estimado: ${total_prov:,.2f}\n"
        mensaje += "\nGracias.\nSistema de Cafeteria"

        # Obtener email del proveedor si se envia a proveedores
        if enviar_a_proveedores:
            proveedor = Proveedor.query.filter_by(nombre=prov_nombre).first()
            destinatario = proveedor.email if proveedor and proveedor.email else None
        else:
            destinatario = email_from  # Enviar a mi mismo

        if destinatario and email_from and email_pass:
            try:
                msg = MIMEMultipart()
                msg['From'] = email_from
                msg['To'] = destinatario
                msg['Subject'] = f"Pedido Cafeteria - {fecha}"
                msg.attach(MIMEText(mensaje, 'plain'))

                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(email_from, email_pass)
                server.send_message(msg)
                server.quit()
                enviados.append(prov_nombre)
            except Exception as e:
                errores.append(f"{prov_nombre}: {str(e)[:50]}")
        else:
            if enviar_a_proveedores:
                errores.append(f"{prov_nombre}: Sin email configurado")

    # Guardar compras en historial
    if enviados:
        for item in items:
            compra = Compra(
                producto=item['producto'],
                proveedor=item['proveedor'],
                tiempo_entrega=item.get('tiempo', '1'),
                cantidad=float(item['cantidad']),
                costo_unitario=float(item['precio']),
                iva_porcentaje=0,
                total_final=float(item['cantidad']) * float(item['precio']),
                usuario=current_user.username
            )
            db.session.add(compra)
        db.session.commit()

    return jsonify({
        'success': len(enviados) > 0,
        'enviados': enviados,
        'errores': errores
    })

# --- HISTORIAL ---
@app.route('/historial')
@login_required
def historial():
    if current_user.rol != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))

    compras_list = Compra.query.order_by(Compra.id.desc()).all()
    return render_template('historial.html', compras=compras_list)

# --- USUARIOS ---
@app.route('/usuarios', methods=['GET', 'POST'])
@login_required
def usuarios():
    if current_user.rol != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        rol = request.form.get('rol', 'empleado')

        if username and password:
            if Usuario.query.filter_by(username=username).first():
                flash('Este usuario ya existe', 'error')
            else:
                user = Usuario(username=username, rol=rol)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash(f'Usuario "{username}" creado', 'success')
        else:
            flash('Usuario y contrasena son obligatorios', 'error')

        return redirect(url_for('usuarios'))

    usuarios_list = Usuario.query.all()
    return render_template('usuarios.html', usuarios=usuarios_list)

@app.route('/usuarios/eliminar/<int:id>')
@login_required
def eliminar_usuario(id):
    if current_user.rol != 'admin':
        flash('Acceso denegado', 'error')
        return redirect(url_for('dashboard'))

    user = Usuario.query.get_or_404(id)
    if user.username == 'admin':
        flash('No puedes eliminar el usuario admin', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash(f'Usuario "{user.username}" eliminado', 'success')

    return redirect(url_for('usuarios'))


if __name__ == '__main__':
    app.run(debug=True)
