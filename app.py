from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from datetime import datetime, timedelta
import pytz
import os
from flask import send_file
from psycopg2.extras import DictCursor
import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name='dcbdjnpzo',
    api_key='381622333637456',
    api_secret='P1Pzvu85aCR02HuRSCnz76yzrgg'
)

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Necesario para usar sesiones

# Configuración de la conexión a PostgreSQL
import os
import psycopg2
import psycopg2.extras

def get_db_connection():
    # Usa DictCursor para que fetchone() y fetchall() devuelvan dicts
    conn = psycopg2.connect(
        os.environ["DATABASE_URL"],
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    return conn

# Crear tabla de usuarios si no existe
def crear_tabla_usuarios():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')
    conn.commit()
    conn.close()

# Llamar a la función para crear la tabla de usuarios al iniciar la aplicación
crear_tabla_usuarios()

# Función para crear la tabla `equipos` si no existe
def crear_tabla_equipos():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS equipos_isaias (
            id SERIAL PRIMARY KEY,
            tipo_reparacion TEXT NOT NULL,
            marca TEXT NOT NULL,
            modelo TEXT NOT NULL,
            tecnico TEXT NOT NULL,
            monto REAL NOT NULL,
            nombre_cliente TEXT NOT NULL,
            telefono TEXT NOT NULL,
            nro_orden TEXT NOT NULL,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

# Llamar a la función para crear la tabla al iniciar la aplicación
crear_tabla_equipos()

# Proteger rutas que requieren autenticación
def login_required(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Debes iniciar sesión para acceder a esta página.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta principal (redirige al login si no está autenticado)
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('inicio'))  # Redirige a la página principal del sistema
    return redirect(url_for('login'))  # Redirige al login si no está autenticado


# Ruta para el login
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya está autenticado, lo mando directo al inicio
    if 'username' in session:
        return redirect(url_for('inicio'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM usuarios WHERE username = %s', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and user['password'] == password:
            # Guardamos sesión
            session['username'] = user['username']
            session['role'] = user['role']

            return redirect(url_for('inicio'))
        else:
            flash('Usuario o contraseña incorrectos', 'error')

    return render_template('login.html')


# Ruta para la página principal del sistema (después del login)
@app.route('/inicio')
def inicio():
    if 'username' not in session:
        return redirect(url_for('login'))  # Redirige al login si no está autenticado
    return render_template('inicio.html')

# Ruta para el logout
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('role', None)
    flash('Has cerrado sesión correctamente.', 'success')
    return redirect(url_for('login'))

# Ruta para registrar ventas
# Ruta para registrar ventas
@app.route('/registrar_venta', methods=['GET', 'POST'])
def registrar_venta():
    conn = get_db_connection()
    cursor = conn.cursor()

    if 'carrito' not in session:
        session['carrito'] = []

    if request.method == 'POST':
        if 'buscar' in request.form:
            busqueda = request.form['busqueda']
            cursor.execute('''
                SELECT id, nombre, codigo_barras, stock, precio 
                FROM productos_isaias
                WHERE codigo_barras = %s OR nombre ILIKE %s
            ''', (busqueda, f'%{busqueda}%'))
            productos = cursor.fetchall()
            conn.close()
            return render_template('registrar_venta.html', productos=productos, carrito=session['carrito'])

        elif 'agregar' in request.form:
            producto_id = request.form['producto_id']
            cantidad = int(request.form['cantidad'])

            cursor.execute('SELECT id, nombre, precio, stock FROM productos_isaias WHERE id = %s', (producto_id,))
            producto = cursor.fetchone()

            if producto and producto['precio'] is not None:
                if producto['stock'] >= cantidad:
                    item = {
                        'id': producto['id'],
                        'nombre': producto['nombre'],
                        'precio': float(producto['precio']),
                        'cantidad': cantidad
                    }
                    session['carrito'].append(item)
                    session.modified = True
                else:
                    flash(f'Sin stock suficiente para "{producto["nombre"]}"', 'error')
            else:
                flash('Producto no encontrado o sin precio', 'error')

        elif 'agregar_manual' in request.form:
            nombre = request.form['nombre_manual']
            precio = float(request.form['precio_manual'])
            cantidad = int(request.form['cantidad_manual'])

            item = {
                'id': None,
                'nombre': nombre,
                'precio': precio,
                'cantidad': cantidad
            }
            session['carrito'].append(item)
            session.modified = True
            flash(f'Servicio técnico "{nombre}" agregado al carrito', 'success')

        elif 'registrar' in request.form:
            if not session['carrito']:
                flash('El carrito está vacío', 'error')
                return redirect(url_for('registrar_venta'))

            tipo_pago = request.form.get('tipo_pago') or request.form.get('tipo_pago_1')
            dni_cliente = request.form['dni_cliente']
            argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
            fecha_actual = datetime.now(argentina_tz).strftime('%Y-%m-%d %H:%M:%S')

            for item in session['carrito']:
                producto_id = item['id']
                nombre = item['nombre']
                precio = float(item['precio'])
                cantidad = int(item['cantidad'])

                if producto_id is not None:
                    cursor.execute('SELECT stock FROM productos_isaias WHERE id = %s', (producto_id,))
                    producto = cursor.fetchone()

                    if producto and producto['stock'] >= cantidad:
                        cursor.execute('''
                            INSERT INTO ventas_isaias 
                            (producto_id, cantidad, fecha, nombre_manual, precio_manual, tipo_pago, dni_cliente, nombre_producto, precio_unitario)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ''', (
                            producto_id, cantidad, fecha_actual, None, None, tipo_pago, dni_cliente, nombre, precio
                        ))
                        cursor.execute('UPDATE productos_isaias SET stock = stock - %s WHERE id = %s', (cantidad, producto_id))
                    else:
                        conn.close()
                        flash(f'Sin stock para el producto: {nombre}', 'error')
                        return redirect(url_for('registrar_venta'))
                else:
                    cursor.execute('''
                        INSERT INTO reparaciones_isaias (nombre_servicio, precio, cantidad, tipo_pago, dni_cliente, fecha)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (nombre, precio, cantidad, tipo_pago, dni_cliente, fecha_actual))

            conn.commit()
            conn.close()
            session.pop('carrito', None)
            flash('Venta registrada con éxito', 'success')
            return redirect(url_for('registrar_venta'))

        elif 'vaciar' in request.form:
            session.pop('carrito', None)
            flash('Carrito vaciado', 'success')
            return redirect(url_for('registrar_venta'))

    total = sum(float(item['precio']) * int(item['cantidad']) for item in session['carrito'])
    conn.close()
    return render_template('registrar_venta.html', productos=None, carrito=session['carrito'], total=total)


# Ruta para mostrar los productos más vendidos
@app.route('/productos_mas_vendidos')
def productos_mas_vendidos():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Consulta corregida con GROUP BY correcto
    cursor.execute('''
        SELECT 
            COALESCE(v.nombre_producto, p.nombre) AS nombre,
            COALESCE(v.precio_unitario, p.precio) AS precio,
            SUM(v.cantidad) AS cantidad_vendida
        FROM ventas_isaias v
        LEFT JOIN productos_isaias p ON v.producto_id = p.id
        GROUP BY COALESCE(v.nombre_producto, p.nombre), COALESCE(v.precio_unitario, p.precio)
        ORDER BY cantidad_vendida DESC
        LIMIT 5
    ''')
    productos = cursor.fetchall()

    # Calcular total unidades vendidas
    cursor.execute('SELECT SUM(cantidad) FROM ventas_isaias')
    total_ventas = cursor.fetchone()[0] or 0

    productos_con_porcentaje = []
    for producto in productos:
        nombre, precio, cantidad_vendida = producto
        porcentaje = (cantidad_vendida / total_ventas) * 100 if total_ventas > 0 else 0
        productos_con_porcentaje.append({
            'nombre': nombre,
            'precio': precio,
            'cantidad_vendida': cantidad_vendida,
            'porcentaje': round(porcentaje, 2)
        })

    conn.close()
    return render_template('productos_mas_vendidos.html', productos=productos_con_porcentaje, total_ventas=total_ventas)


# Ruta para productos por agotarse
@app.route('/productos_por_agotarse')
def productos_por_agotarse():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Obtener productos con stock menor o igual a 2
    cursor.execute('''
    SELECT id, nombre, codigo_barras, stock, precio, precio_costo
    FROM productos_isaias
    WHERE stock <= 2
    ORDER BY stock ASC
    ''')
    productos = cursor.fetchall()

    conn.close()
    return render_template('productos_por_agotarse.html', productos=productos)

# Ruta principal para mostrar las ventas y reparaciones
from flask import send_file
from openpyxl import Workbook
from io import BytesIO

@app.route('/ultimas_ventas')
def ultimas_ventas():
    conn = get_db_connection()
    cursor = conn.cursor()

    argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
    fecha_actual = datetime.now(argentina_tz).strftime('%Y-%m-%d')

    fecha_desde = request.args.get('fecha_desde', fecha_actual)
    fecha_hasta = request.args.get('fecha_hasta', fecha_actual)
    exportar = request.args.get('exportar', False)

    # Usar nombre_producto y precio_unitario directamente
    cursor.execute('''
        SELECT 
            id AS venta_id,
            nombre_producto,
            cantidad,
            precio_unitario,
            (cantidad * precio_unitario) AS total,
            fecha,
            tipo_pago,
            dni_cliente
        FROM ventas_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
        ORDER BY fecha DESC
    ''', (fecha_desde, fecha_hasta))
    ventas = cursor.fetchall()

    if exportar:
        wb = Workbook()
        ws = wb.active
        ws.title = "Ventas"
        ws.append(["ID Venta", "Producto", "Cantidad", "Precio Unitario", "Total", "Fecha", "Tipo de Pago", "DNI Cliente"])

        for venta in ventas:
            ws.append([
                venta['venta_id'],
                venta['nombre_producto'],
                venta['cantidad'],
                float(venta['precio_unitario']),
                float(venta['total']),
                venta['fecha'].strftime('%Y-%m-%d %H:%M:%S') if venta['fecha'] else '',
                venta['tipo_pago'],
                venta['dni_cliente'] or ''
            ])

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        nombre_archivo = f"ventas_{fecha_desde}_a_{fecha_hasta}.xlsx"
        return send_file(
            output,
            as_attachment=True,
            download_name=nombre_archivo,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    # Reparaciones
    cursor.execute('''
        SELECT 
            id AS reparacion_id,
            nombre_servicio,
            cantidad,
            precio AS precio_unitario,
            (cantidad * precio) AS total,
            fecha,
            tipo_pago
        FROM reparaciones_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
        ORDER BY fecha DESC
    ''', (fecha_desde, fecha_hasta))
    reparaciones = cursor.fetchall()

    total_ventas_por_pago = {}
    for venta in ventas:
        tipo = venta['tipo_pago']
        total = float(venta['total'])
        total_ventas_por_pago[tipo] = total_ventas_por_pago.get(tipo, 0.0) + total

    total_reparaciones_por_pago = {}
    for r in reparaciones:
        tipo = r['tipo_pago']
        total = float(r['total'])
        total_reparaciones_por_pago[tipo] = total_reparaciones_por_pago.get(tipo, 0.0) + total

    conn.close()

    return render_template(
        'ultimas_ventas.html',
        ventas=ventas,
        reparaciones=reparaciones,
        fecha_actual=fecha_actual,
        total_ventas_por_pago=total_ventas_por_pago,
        total_reparaciones_por_pago=total_reparaciones_por_pago,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta
    )


@app.route('/anular_venta/<int:venta_id>', methods=['POST'])
def anular_venta(venta_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Buscar la venta por ID
        cursor.execute('SELECT * FROM ventas_isaias WHERE id = %s', (venta_id,))
        venta = cursor.fetchone()

        if not venta:
            return jsonify({'success': False, 'message': 'Venta no encontrada'}), 404

        producto_id = venta['producto_id']
        cantidad = venta['cantidad']

        # Restaurar stock solo si existe el producto asociado
        if producto_id:
            cursor.execute('SELECT id FROM productos_isaias WHERE id = %s', (producto_id,))
            producto = cursor.fetchone()
            if producto:
                cursor.execute('UPDATE productos_isaias SET stock = stock + %s WHERE id = %s', (cantidad, producto_id))

        # Eliminar la venta
        cursor.execute('DELETE FROM ventas_isaias WHERE id = %s', (venta_id,))
        conn.commit()

        return jsonify({'success': True, 'message': 'Venta anulada correctamente'}), 200

    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()


# Ruta para eliminar una reparación
@app.route('/anular_reparacion/<int:reparacion_id>', methods=['POST'])
def anular_reparacion(reparacion_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Verificar si la reparación existe
        cursor.execute('SELECT * FROM reparaciones_isaias WHERE id = %s', (reparacion_id,))
        reparacion = cursor.fetchone()

        if not reparacion:
            return jsonify({'success': False, 'message': 'Reparación no encontrada'}), 404

        # Eliminar la reparación
        cursor.execute('DELETE FROM reparaciones_isaias WHERE id = %s', (reparacion_id,))
        conn.commit()

        return jsonify({'success': True, 'message': 'Reparación eliminada correctamente'}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        conn.close()

# Ruta para egresos
@app.route('/egresos', methods=['GET', 'POST'])
def egresos():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Agregar un nuevo egreso
    if request.method == 'POST' and 'agregar' in request.form:
        fecha = request.form['fecha']
        monto = float(request.form['monto'])
        descripcion = request.form['descripcion']
        tipo_pago = request.form['tipo_pago']  # Nuevo campo

        cursor.execute('''
        INSERT INTO egresos_isaias (fecha, monto, descripcion, tipo_pago)
        VALUES (%s, %s, %s, %s)
        ''', (fecha, monto, descripcion, tipo_pago))
        conn.commit()
        conn.close()
        return redirect(url_for('egresos'))

    # Eliminar un egreso
    if request.method == 'POST' and 'eliminar' in request.form:
        egreso_id = request.form['egreso_id']
        cursor.execute('DELETE FROM egresos_isaias WHERE id = %s', (egreso_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('egresos'))

    # Obtener todos los egresos
    cursor.execute('SELECT id, fecha, monto, descripcion, tipo_pago FROM egresos_isaias ORDER BY fecha DESC')
    egresos = cursor.fetchall()
    conn.close()
    return render_template('egresos.html', egresos=egresos)

from decimal import Decimal

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    fecha_desde = request.args.get('fecha_desde', datetime.now().strftime('%Y-%m-%d'))
    fecha_hasta = request.args.get('fecha_hasta', datetime.now().strftime('%Y-%m-%d'))

    # Total ventas productos
    cursor.execute('''
        SELECT SUM(cantidad * COALESCE(precio_unitario, 0)) AS total_ventas_productos
        FROM ventas_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta))
    total_ventas_productos = cursor.fetchone()['total_ventas_productos'] or 0

    # Total ventas reparaciones
    cursor.execute('''
        SELECT SUM(precio) AS total_ventas_reparaciones
        FROM reparaciones_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta))
    total_ventas_reparaciones = cursor.fetchone()['total_ventas_reparaciones'] or 0

    if isinstance(total_ventas_productos, Decimal):
        total_ventas_productos = float(total_ventas_productos)
    if isinstance(total_ventas_reparaciones, Decimal):
        total_ventas_reparaciones = float(total_ventas_reparaciones)

    total_ventas = total_ventas_productos + total_ventas_reparaciones

    # Total egresos
    cursor.execute('''
        SELECT SUM(monto) AS total_egresos
        FROM egresos_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta))
    total_egresos = cursor.fetchone()['total_egresos'] or 0
    if isinstance(total_egresos, Decimal):
        total_egresos = float(total_egresos)

    # Total costo
    cursor.execute('''
        SELECT SUM(v.cantidad * COALESCE(p.precio_costo, 0)) AS total_costo
        FROM ventas_isaias v
        LEFT JOIN productos_isaias p ON v.producto_id = p.id
        WHERE DATE(v.fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta))
    total_costo = cursor.fetchone()['total_costo'] or 0
    if isinstance(total_costo, Decimal):
        total_costo = float(total_costo)

    # Stock actual
    cursor.execute('SELECT SUM(stock * precio_costo) AS total_costo_stock FROM productos_isaias')
    total_costo_stock = cursor.fetchone()['total_costo_stock'] or 0
    cursor.execute('SELECT SUM(stock * precio) AS total_venta_stock FROM productos_isaias')
    total_venta_stock = cursor.fetchone()['total_venta_stock'] or 0
    cursor.execute('SELECT SUM(stock) AS cantidad_total_stock FROM productos_isaias')
    cantidad_total_stock = cursor.fetchone()['cantidad_total_stock'] or 0

    if isinstance(total_costo_stock, Decimal):
        total_costo_stock = float(total_costo_stock)
    if isinstance(total_venta_stock, Decimal):
        total_venta_stock = float(total_venta_stock)
    if isinstance(cantidad_total_stock, Decimal):
        cantidad_total_stock = float(cantidad_total_stock)

    # Ventas mensuales
    cursor.execute('''
        SELECT TO_CHAR(fecha, 'YYYY-MM') AS mes, SUM(cantidad * COALESCE(precio_unitario, 0)) AS total
        FROM ventas_isaias
        GROUP BY mes ORDER BY mes
    ''')
    ventas_productos = cursor.fetchall()

    cursor.execute('''
        SELECT TO_CHAR(fecha, 'YYYY-MM') AS mes, SUM(cantidad * precio) AS total
        FROM reparaciones_isaias
        GROUP BY mes ORDER BY mes
    ''')
    ventas_reparaciones = cursor.fetchall()

    ventas_dict = {}
    for row in ventas_productos:
        total = float(row['total']) if isinstance(row['total'], Decimal) else row['total']
        ventas_dict[row['mes']] = ventas_dict.get(row['mes'], 0) + total
    for row in ventas_reparaciones:
        total = float(row['total']) if isinstance(row['total'], Decimal) else row['total']
        ventas_dict[row['mes']] = ventas_dict.get(row['mes'], 0) + total

    ventas_mensuales = [{'mes': mes, 'total': round(ventas_dict[mes], 2)} for mes in sorted(ventas_dict)]

    # Ventas semanales
    cursor.execute('''
        SELECT TO_CHAR(DATE_TRUNC('week', fecha), 'YYYY-MM-DD') AS semana,
               SUM(cantidad * COALESCE(precio_unitario, 0)) AS total
        FROM ventas_isaias
        GROUP BY semana ORDER BY semana
    ''')
    ventas_prod_sem = cursor.fetchall()

    cursor.execute('''
        SELECT TO_CHAR(DATE_TRUNC('week', fecha), 'YYYY-MM-DD') AS semana,
               SUM(cantidad * precio) AS total
        FROM reparaciones_isaias
        GROUP BY semana ORDER BY semana
    ''')
    ventas_rep_sem = cursor.fetchall()

    ventas_dict_semanal = {}
    for row in ventas_prod_sem:
        total = float(row['total']) if isinstance(row['total'], Decimal) else row['total']
        ventas_dict_semanal[row['semana']] = ventas_dict_semanal.get(row['semana'], 0) + total
    for row in ventas_rep_sem:
        total = float(row['total']) if isinstance(row['total'], Decimal) else row['total']
        ventas_dict_semanal[row['semana']] = ventas_dict_semanal.get(row['semana'], 0) + total

    ventas_semanales = [{'semana': semana, 'total': round(ventas_dict_semanal[semana], 2)} for semana in sorted(ventas_dict_semanal)]

    ganancia = total_ventas - total_egresos - total_costo

    cursor.execute('''
        SELECT 'Productos' AS tipo, SUM(cantidad * COALESCE(precio_unitario, 0)) AS total
        FROM ventas_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
        UNION ALL
        SELECT 'Reparaciones' AS tipo, SUM(precio) AS total
        FROM reparaciones_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
    ''', (fecha_desde, fecha_hasta, fecha_desde, fecha_hasta))
    distribucion_ventas = cursor.fetchall()

    conn.close()

    return render_template('dashboard.html',
        total_ventas=total_ventas,
        total_egresos=total_egresos,
        total_costo=total_costo,
        ganancia=ganancia,
        total_ventas_productos=total_ventas_productos,
        total_ventas_reparaciones=total_ventas_reparaciones,
        distribucion_ventas=distribucion_ventas,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        total_costo_stock=total_costo_stock,
        total_venta_stock=total_venta_stock,
        ventas_mensuales=ventas_mensuales,
        ventas_semanales=ventas_semanales,
        cantidad_total_stock=cantidad_total_stock
    )



@app.route('/resumen_semanal')
def resumen_semanal():
    hoy = datetime.now()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana_str = inicio_semana.strftime('%Y-%m-%d')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Corregido: calcular el total con cantidad * precio_unitario
    cursor.execute('''
        SELECT tipo_pago, SUM(cantidad * precio_unitario) AS total
        FROM ventas_isaias
        WHERE fecha >= %s
        GROUP BY tipo_pago
    ''', (inicio_semana_str,))
    resumen = cursor.fetchall()

    conn.close()

    return render_template('resumen_semanal.html', resumen=resumen)

from decimal import Decimal

@app.route('/caja')
def caja():
    conn = get_db_connection()
    cursor = conn.cursor()

    argentina_tz = pytz.timezone('America/Argentina/Buenos_Aires')
    hoy = datetime.now(argentina_tz).date()

    fecha_desde = request.args.get('fecha_desde', hoy.strftime('%Y-%m-%d'))
    fecha_hasta = request.args.get('fecha_hasta', hoy.strftime('%Y-%m-%d'))

    # Ventas
    cursor.execute('''
        SELECT 
            v.id AS venta_id,
            COALESCE(v.nombre_producto, p.nombre) AS nombre_producto,
            v.cantidad,
            COALESCE(v.precio_unitario, p.precio) AS precio_unitario,
            (v.cantidad * COALESCE(v.precio_unitario, p.precio)) AS total,
            v.fecha,
            v.tipo_pago
        FROM ventas_isaias v
        LEFT JOIN productos_isaias p ON v.producto_id = p.id
        WHERE DATE(v.fecha) BETWEEN %s AND %s
        ORDER BY v.fecha DESC
    ''', (fecha_desde, fecha_hasta))
    ventas = cursor.fetchall()

    # Reparaciones
    cursor.execute('''
        SELECT 
            id AS reparacion_id,
            nombre_servicio,
            cantidad,
            precio AS precio_unitario,
            (cantidad * precio) AS total,
            fecha,
            tipo_pago
        FROM reparaciones_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
        ORDER BY fecha DESC
    ''', (fecha_desde, fecha_hasta))
    reparaciones = cursor.fetchall()

    # Egresos
    cursor.execute('''
        SELECT 
            id AS egreso_id,
            descripcion,
            monto,
            tipo_pago,
            fecha
        FROM egresos_isaias
        WHERE DATE(fecha) BETWEEN %s AND %s
        ORDER BY fecha DESC
    ''', (fecha_desde, fecha_hasta))
    egresos = cursor.fetchall()

    # Totales
    def to_float(val):
        return float(val) if val is not None else 0.0

    total_ventas_por_pago = {}
    for v in ventas:
        tipo = v['tipo_pago']
        total = to_float(v['total'])
        total_ventas_por_pago[tipo] = total_ventas_por_pago.get(tipo, 0) + total

    total_reparaciones_por_pago = {}
    for r in reparaciones:
        tipo = r['tipo_pago']
        total = to_float(r['total'])
        total_reparaciones_por_pago[tipo] = total_reparaciones_por_pago.get(tipo, 0) + total

    total_combinado_por_pago = total_ventas_por_pago.copy()
    for tipo, total in total_reparaciones_por_pago.items():
        total_combinado_por_pago[tipo] = total_combinado_por_pago.get(tipo, 0) + total

    total_egresos_por_pago = {}
    for e in egresos:
        tipo = e['tipo_pago']
        monto = to_float(e['monto'])
        total_egresos_por_pago[tipo] = total_egresos_por_pago.get(tipo, 0) + monto

    neto_por_pago = {}
    for tipo, total in total_combinado_por_pago.items():
        egresos_tipo = total_egresos_por_pago.get(tipo, 0)
        neto_por_pago[tipo] = total - egresos_tipo

    conn.close()

    return render_template(
        'caja.html',
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        neto_por_pago=neto_por_pago
    )


# Ruta para reparaciones
import unicodedata

def normalizar(texto):
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode().lower().strip()

# Ruta para reparaciones
import unicodedata

def normalizar(texto):
    return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode().lower().strip()

@app.route('/reparaciones', methods=['GET', 'POST'])
def reparaciones():
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        tipo_reparacion = request.form['tipo_reparacion']
        marca = request.form['equipo']
        modelo = request.form['modelo']
        tecnico = request.form['tecnico']
        monto = float(request.form['monto'])
        nombre_cliente = request.form['nombre_cliente']
        telefono = request.form['telefono']
        observaciones = request.form.get('observaciones', '')
        fecha = datetime.now().date()
        hora = datetime.now().strftime('%H:%M:%S')
        estado = 'Por Reparar'

        # Generar nro_orden automático en formato AAMM-N
        hoy = datetime.now()
        prefijo = hoy.strftime('%y%m')  # AAMM
        cursor.execute('''
            SELECT nro_orden FROM equipos_isaias 
            WHERE nro_orden LIKE %s
            ORDER BY id DESC LIMIT 1
        ''', (f'{prefijo}-%',))
        ultimo = cursor.fetchone()

        if ultimo:
            ultimo_numero = int(ultimo['nro_orden'].split('-')[-1])
            nuevo_numero = ultimo_numero + 1
        else:
            nuevo_numero = 1

        nro_orden = f"{prefijo}-{nuevo_numero}"

        cursor.execute('''
            INSERT INTO equipos_isaias (
                tipo_reparacion, marca, modelo, tecnico, monto,
                nombre_cliente, telefono, nro_orden, fecha, hora, estado, observaciones
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            tipo_reparacion, marca, modelo, tecnico, monto,
            nombre_cliente, telefono, nro_orden, fecha, hora, estado, observaciones
        ))
        conn.commit()

    # Fechas desde GET
    fecha_desde = request.args.get('fecha_desde', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
    fecha_hasta = request.args.get('fecha_hasta', datetime.now().strftime('%Y-%m-%d'))

    # Últimos equipos ordenados por fecha y hora descendente
    cursor.execute('''
        SELECT * FROM equipos_isaias
        WHERE fecha BETWEEN %s AND %s
        ORDER BY fecha DESC, hora DESC
    ''', (fecha_desde, fecha_hasta))
    ultimos_equipos = cursor.fetchall()

    # Por técnico
    cursor.execute('''
        SELECT tecnico, COUNT(*) as cantidad
        FROM equipos_isaias
        WHERE fecha BETWEEN %s AND %s
        GROUP BY tecnico
    ''', (fecha_desde, fecha_hasta))
    datos_tecnicos = cursor.fetchall()
    equipos_por_tecnico = {row['tecnico']: row['cantidad'] for row in datos_tecnicos}

    # Por estado
    cursor.execute('''
        SELECT estado, COUNT(*) as cantidad
        FROM equipos_isaias
        WHERE fecha BETWEEN %s AND %s
        GROUP BY estado
    ''', (fecha_desde, fecha_hasta))
    datos_estados = cursor.fetchall()

    estados = {
        'por_reparar': 0,
        'en_reparacion': 0,
        'listo': 0,
        'retirado': 0,
        'no_salio': 0
    }

    for row in datos_estados:
        estado = normalizar(row['estado'])
        cantidad = row['cantidad']

        if estado in ['por reparar', 'por_reparar']:
            estados['por_reparar'] += cantidad
        elif estado in ['en reparacion', 'en reparación', 'en_reparacion']:
            estados['en_reparacion'] += cantidad
        elif estado == 'listo':
            estados['listo'] += cantidad
        elif estado == 'retirado':
            estados['retirado'] += cantidad
        elif estado in ['no salio', 'no_salio']:
            estados['no_salio'] += cantidad
        else:
            estados[estado] = cantidad

    estados['total'] = sum([
        cantidad for key, cantidad in estados.items()
        if key != 'total'
    ])

    conn.close()

    return render_template(
        'reparaciones.html',
        ultimos_equipos=ultimos_equipos,
        equipos_por_tecnico=equipos_por_tecnico,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        estados=estados
    )



# Ruta para eliminar reparaciones
@app.route('/eliminar_reparacion/<int:id>', methods=['POST'])
def eliminar_reparacion(id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Eliminar el equipo por su ID
    cursor.execute('DELETE FROM equipos_isaias WHERE id = %s', (id,))
    conn.commit()
    conn.close()

    # Redirigir a la página de reparaciones después de eliminar
    return redirect(url_for('reparaciones'))

# Ruta para actualizar estado de reparaciones
@app.route('/actualizar_estado', methods=['POST'])
def actualizar_estado():
    data = request.get_json()
    nro_orden = data['nro_orden']
    estado = data['estado']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE equipos_isaias
        SET estado = %s
        WHERE nro_orden = %s
    ''', (estado, nro_orden))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

# Ruta para mercadería fallada
@app.route('/mercaderia_fallada', methods=['GET', 'POST'])
def mercaderia_fallada():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Buscar productos
    if request.method == 'POST' and 'buscar' in request.form:
        busqueda = request.form['busqueda']
        cursor.execute('''
        SELECT id, nombre, codigo_barras, stock, precio, precio_costo
        FROM productos_isaias
        WHERE nombre LIKE %s OR codigo_barras LIKE %s
        ''', (f'%{busqueda}%', f'%{busqueda}%'))
        productos = cursor.fetchall()
        conn.close()
        return render_template('mercaderia_fallada.html', productos=productos)

    # Registrar mercadería fallada
    if request.method == 'POST' and 'registrar_fallada' in request.form:
        producto_id = request.form['producto_id']
        cantidad = int(request.form['cantidad'])
        descripcion = request.form['descripcion']
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Verificar si hay suficiente stock
        cursor.execute('SELECT stock FROM productos_isaias WHERE id = %s', (producto_id,))
        producto = cursor.fetchone()

        if producto and producto['stock'] >= cantidad:
            # Registrar en la tabla `mercaderia_fallada_isaias`
            cursor.execute('''
            INSERT INTO mercaderia_fallada_isaias (producto_id, cantidad, fecha, descripcion)
            VALUES (%s, %s, %s, %s)
            ''', (producto_id, cantidad, fecha, descripcion))

            # Actualizar el stock en la tabla `productos`
            cursor.execute('UPDATE productos_isaias SET stock = stock - %s WHERE id = %s', (cantidad, producto_id))
            conn.commit()
            conn.close()
            return redirect(url_for('mercaderia_fallada_isaias'))
        else:
            conn.close()
            return f"No hay suficiente stock para el producto seleccionado."

    # Obtener historial de mercadería fallada
    cursor.execute('''
    SELECT mf.id, p.nombre, mf.cantidad, mf.fecha, mf.descripcion
    FROM mercaderia_fallada_isaias mf
    JOIN productos_isaias p ON mf.producto_id = p.id
    ORDER BY mf.fecha DESC
    ''')
    historial = cursor.fetchall()

    conn.close()
    return render_template('mercaderia_fallada.html', historial=historial)


@app.route("/cotizar")
def cotizar():
    return render_template("cotizar.html")


@app.route('/agregar_stock', methods=['GET', 'POST'])
def agregar_stock():
    conn = get_db_connection()
    cursor = conn.cursor()

    categorias = ['Repuestos', 'Fundas', 'Cargadores', 'Auriculares']

    # Obtener el término de búsqueda (si existe)
    busqueda = request.args.get('busqueda', '')

    try:
        # Eliminar un producto y desvincular ventas
        if request.method == 'POST' and 'eliminar' in request.form:
            producto_id = request.form['producto_id']

            # Desvincular producto de ventas antes de eliminar
            cursor.execute('UPDATE ventas_isaias SET producto_id = NULL WHERE producto_id = %s', (producto_id,))
            cursor.execute('DELETE FROM productos_isaias WHERE id = %s', (producto_id,))
            conn.commit()
            return redirect(url_for('agregar_stock'))

        # Editar un producto
        if request.method == 'POST' and 'editar' in request.form:
            producto_id = request.form['producto_id']
            nombre = request.form['nombre'].upper()
            codigo_barras = request.form['codigo_barras']
            stock = int(request.form['stock'])
            precio = float(request.form['precio'])
            precio_costo = float(request.form['precio_costo'])
            categoria = request.form.get('categoria')

            foto_url = None
            if 'foto' in request.files:
                foto = request.files['foto']
                if foto and foto.filename != '':
                    result = cloudinary.uploader.upload(foto)
                    foto_url = result['secure_url']

            if foto_url:
                cursor.execute('''
                    UPDATE productos_isaias
                    SET nombre = %s, codigo_barras = %s, stock = %s, precio = %s, precio_costo = %s, categoria = %s, foto_url = %s
                    WHERE id = %s
                ''', (nombre, codigo_barras, stock, precio, precio_costo, categoria, foto_url, producto_id))
            else:
                cursor.execute('''
                    UPDATE productos_isaias
                    SET nombre = %s, codigo_barras = %s, stock = %s, precio = %s, precio_costo = %s, categoria = %s
                    WHERE id = %s
                ''', (nombre, codigo_barras, stock, precio, precio_costo, categoria, producto_id))
            
            conn.commit()
            return redirect(url_for('agregar_stock'))

        # Agregar stock a un producto existente
        if request.method == 'POST' and 'agregar_stock' in request.form:
            producto_id = request.form['producto_id']
            cantidad = int(request.form['cantidad'])

            cursor.execute('''
                UPDATE productos_isaias
                SET stock = stock + %s
                WHERE id = %s
            ''', (cantidad, producto_id))
            conn.commit()
            return redirect(url_for('agregar_stock'))

        # Agregar un nuevo producto (con imagen y categoría)
        if request.method == 'POST' and 'agregar' in request.form:
            nombre = request.form['nombre'].upper()
            codigo_barras = request.form['codigo_barras']
            stock = int(request.form['stock'])
            precio = float(request.form['precio'])
            precio_costo = float(request.form['precio_costo'])
            categoria = request.form.get('categoria')

            foto_url = None
            if 'foto' in request.files:
                foto = request.files['foto']
                if foto and foto.filename != '':
                    result = cloudinary.uploader.upload(foto)
                    foto_url = result['secure_url']

            cursor.execute('''
                INSERT INTO productos_isaias (nombre, codigo_barras, stock, precio, precio_costo, foto_url, categoria)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (nombre, codigo_barras, stock, precio, precio_costo, foto_url, categoria))
            conn.commit()
            return redirect(url_for('agregar_stock'))

        # Obtener productos filtrados por búsqueda (si existe)
        if busqueda:
            cursor.execute('''
                SELECT id, nombre, codigo_barras, stock, precio, precio_costo, foto_url
                FROM productos_isaias
                WHERE nombre LIKE %s OR codigo_barras LIKE %s
            ''', (f'%{busqueda}%', f'%{busqueda}%'))
        else:
            cursor.execute('SELECT id, nombre, codigo_barras, stock, precio, precio_costo, foto_url FROM productos_isaias')

        productos = cursor.fetchall()
        return render_template('agregar_stock.html', productos=productos, busqueda=busqueda, categorias=categorias)

    except Exception as e:
        conn.rollback()
        return f"Error: {str(e)}"
    finally:
        conn.close()



@app.route('/tienda')
def tienda():
    conn = get_db_connection()
    cursor = conn.cursor()

    categoria = request.args.get('categoria')

    if categoria:
        cursor.execute('''
            SELECT id, nombre, codigo_barras, stock, precio, foto_url, categoria
            FROM productos_isaias
            WHERE categoria = %s AND foto_url IS NOT NULL AND stock > 0
            ORDER BY nombre
        ''', (categoria,))
    else:
        cursor.execute('''
            SELECT id, nombre, codigo_barras, stock, precio, foto_url, categoria
            FROM productos_isaias
            WHERE foto_url IS NOT NULL AND stock > 0
            ORDER BY nombre
        ''')

    productos = cursor.fetchall()

    cursor.execute('SELECT DISTINCT categoria FROM productos_isaias WHERE categoria IS NOT NULL ORDER BY categoria')
    categorias = [row[0] for row in cursor.fetchall()]

    conn.close()
    return render_template('tienda.html', productos=productos, categorias=categorias, categoria_seleccionada=categoria)


@app.route('/comprobante/<string:nro_orden>')
def comprobante(nro_orden):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM equipos_isaias WHERE nro_orden = %s', (nro_orden,))
    equipo = cursor.fetchone()
    conn.close()

    if not equipo:
        return "No se encontró la orden", 404

    return render_template("comprobante.html", equipo=equipo)


#----------------NUEVO

@app.route('/firmar')
def firmar():
    nro_orden = request.args.get('nro_orden')
    return render_template('firmar.html', nro_orden=nro_orden)


@app.route('/guardar_firma', methods=['POST'])
def guardar_firma():
    nro_orden = request.form['nro_orden']
    firma_base64 = request.form['firma']

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("UPDATE equipos_isaias SET firma_cliente = %s WHERE nro_orden = %s", (firma_base64, nro_orden))

    conn.commit()
    cur.close()
    conn.close()

    return "Firma guardada correctamente"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

#if __name__ == '__main__':
 #   app.run(debug=True)
