import os
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, Response, abort, flash, redirect, render_template, request, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from models import (
    LEN_CODIGO_POSTAL,
    ROL_ADMIN,
    ROL_SOCIO,
    Administrador,
    Alquiler,
    Estadistica,
    Pelicula,
    Socio,
    Usuario,
    Videoclub,
    db,
)

load_dotenv()

ROUTE_INDEX = 'index'
ROUTE_LOGIN = 'login'
ROUTE_REGISTRO = 'registro'
ROUTE_VIDEOCLUBS = 'gestionar_videoclubs'
ROUTE_PELICULAS = 'gestionar_peliculas'
ROUTE_SOCIOS = 'gestionar_socios'
ROUTE_ALQUILERES = 'gestionar_alquileres'
ROUTE_ESTADISTICAS = 'gestionar_estadisticas'
ROUTE_ADMINISTRADORES = 'gestionar_administradores'

FLASH_SUCCESS = 'success'
FLASH_DANGER = 'danger'
DATE_FORMAT = '%Y-%m-%d'
MIN_PASSWORD_LEN = 8

MESES_NOMBRES: dict[int, str] = {
    1: 'Enero',
    2: 'Febrero',
    3: 'Marzo',
    4: 'Abril',
    5: 'Mayo',
    6: 'Junio',
    7: 'Julio',
    8: 'Agosto',
    9: 'Septiembre',
    10: 'Octubre',
    11: 'Noviembre',
    12: 'Diciembre',
}

database_url = os.getenv('DATABASE_URL')
if not database_url:
    raise RuntimeError('La variable de entorno DATABASE_URL es obligatoria para iniciar APPV.')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True}
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

csrf = CSRFProtect(app)
db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = ROUTE_LOGIN
login_manager.login_message = 'Inicie sesión para acceder al sistema APPV.'
login_manager.login_message_category = FLASH_DANGER
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id: str) -> Usuario | None:
    return db.session.get(Usuario, int(user_id))


def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not current_user.es_admin:
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped_view


def inicializar_admin_por_defecto() -> None:
    if Administrador.query.count() == 0:
        admin_user = os.getenv('INITIAL_ADMIN_USER', 'admin')
        admin_name = os.getenv('INITIAL_ADMIN_NAME', 'Administrador Principal')
        admin_pass = os.getenv('INITIAL_ADMIN_PASS') or secrets.token_urlsafe(12)

        admin = Administrador(nombre=admin_name)
        db.session.add(admin)
        db.session.flush()

        usuario = Usuario(username=admin_user, rol=ROL_ADMIN, administrador_codigo=admin.codigo)
        usuario.set_password(admin_pass)
        db.session.add(usuario)
        db.session.commit()


with app.app_context():
    db.create_all()
    inicializar_admin_por_defecto()


@app.after_request
def aplicar_cabeceras_seguridad(response: Response) -> Response:
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "style-src 'self' https://cdn.jsdelivr.net; "
        "script-src 'self' https://cdn.jsdelivr.net;"
    )
    return response


def parse_fecha(fecha_str: str) -> date:
    if not fecha_str:
        raise ValueError('La fecha es obligatoria.')
    return datetime.strptime(fecha_str.strip(), DATE_FORMAT).date()


def validar_codigo_postal(cp: str) -> bool:
    return len(cp) == LEN_CODIGO_POSTAL and cp.isdigit()


def existe_pelicula_en_sucursal(nombre: str, videoclub_codigo: int, excluir_codigo: int | None = None) -> bool:
    query = Pelicula.query.filter(
        Pelicula.videoclub_codigo == videoclub_codigo,
        func.lower(func.trim(Pelicula.nombre)) == nombre.strip().lower(),
    )
    if excluir_codigo is not None:
        query = query.filter(Pelicula.codigo != excluir_codigo)
    return query.first() is not None


def guardar_cambios(mensaje_exito: str) -> bool:
    try:
        db.session.commit()
        flash(mensaje_exito, FLASH_SUCCESS)
        return True
    except IntegrityError:
        db.session.rollback()
        flash('Error de integridad en PostgreSQL: el registro ya existe.', FLASH_DANGER)
        return False
    except Exception:
        db.session.rollback()
        flash('Error inesperado al procesar la operación.', FLASH_DANGER)
        return False


# ==================== AUTENTICACIÓN Y REGISTRO ====================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(ROUTE_INDEX))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        usuario = Usuario.query.filter_by(username=username).first()

        if usuario and usuario.check_password(password):
            login_user(usuario)
            flash(f'Bienvenido, {username}.', FLASH_SUCCESS)
            return redirect(url_for(ROUTE_INDEX))

        flash('Credenciales incorrectas.', FLASH_DANGER)

    return render_template('login.html')


@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if current_user.is_authenticated:
        return redirect(url_for(ROUTE_INDEX))

    videoclubs = Videoclub.query.order_by(Videoclub.codigo).all()
    if request.method == 'POST':
        try:
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            nombre = request.form.get('nombre', '').strip()
            edad = int(request.form.get('edad', ''))
            vc_codigo = int(request.form.get('videoclub_codigo', ''))

            if not username or len(password) < MIN_PASSWORD_LEN:
                flash(
                    f'El usuario es obligatorio y la contraseña debe tener al menos {MIN_PASSWORD_LEN} caracteres.',
                    FLASH_DANGER,
                )
                return redirect(url_for(ROUTE_REGISTRO))

            if not nombre or edad <= 0 or not db.session.get(Videoclub, vc_codigo):
                raise ValueError('Datos personales inválidos.')

            nuevo_socio = Socio(nombre=nombre, edad=edad, videoclub_codigo=vc_codigo)
            db.session.add(nuevo_socio)
            db.session.flush()

            nuevo_usuario = Usuario(username=username, rol=ROL_SOCIO, socio_codigo=nuevo_socio.codigo)
            nuevo_usuario.set_password(password)
            db.session.add(nuevo_usuario)

            if guardar_cambios('Registro completado. Ya puede iniciar sesión y alquilar en cualquier videoclub.'):
                return redirect(url_for(ROUTE_LOGIN))
        except ValueError:
            flash('Error: Verifique todos sus datos personales y el videoclub de registro.', FLASH_DANGER)

    return render_template('registro.html', videoclubs=videoclubs)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', FLASH_SUCCESS)
    return redirect(url_for(ROUTE_LOGIN))


# ==================== PANEL PRINCIPAL ====================
@app.route('/', methods=['GET'])
@login_required
def index():
    if current_user.es_admin:
        stats = {
            'videoclubs': Videoclub.query.count(),
            'peliculas': Pelicula.query.count(),
            'socios': Socio.query.count(),
            'alquileres': Alquiler.query.count(),
            'estadisticas': Estadistica.query.count(),
            'administradores': Administrador.query.count(),
        }
    else:
        stats = {
            'videoclubs': Videoclub.query.count(),
            'peliculas': Pelicula.query.count(),
            'alquileres': Alquiler.query.filter_by(socio_codigo=current_user.socio_codigo).count(),
        }
    return render_template('index.html', stats=stats)


# ==================== VIDEOCLUBS ====================
@app.route('/videoclubs', methods=['GET', 'POST'])
@login_required
def gestionar_videoclubs():
    if request.method == 'POST':
        if not current_user.es_admin:
            abort(403)

        cp = request.form.get('codigo_postal', '').strip()
        gerente = request.form.get('nombre_gerente', '').strip()
        ciudad = request.form.get('ciudad', '').strip()
        calle = request.form.get('calle', '').strip()

        if not (gerente and ciudad and calle and validar_codigo_postal(cp)):
            flash('Datos inválidos: todos los campos son obligatorios y el C.P. debe tener 5 dígitos.', FLASH_DANGER)
            return redirect(url_for(ROUTE_VIDEOCLUBS))

        db.session.add(Videoclub(nombre_gerente=gerente, ciudad=ciudad, calle=calle, codigo_postal=cp))
        guardar_cambios('Videoclub registrado correctamente.')
        return redirect(url_for(ROUTE_VIDEOCLUBS))

    return render_template('videoclubs.html', videoclubs=Videoclub.query.order_by(Videoclub.codigo).all())


@app.route('/videoclubs/editar/<int:codigo>', methods=['POST'])
@admin_required
def editar_videoclub(codigo: int):
    vc = db.get_or_404(Videoclub, codigo)
    cp = request.form.get('codigo_postal', '').strip()
    gerente = request.form.get('nombre_gerente', '').strip()
    ciudad = request.form.get('ciudad', '').strip()
    calle = request.form.get('calle', '').strip()

    if not (gerente and ciudad and calle and validar_codigo_postal(cp)):
        flash('Error: Verifique los datos y asegúrese de que el C.P. tenga 5 dígitos.', FLASH_DANGER)
        return redirect(url_for(ROUTE_VIDEOCLUBS))

    vc.nombre_gerente = gerente
    vc.ciudad = ciudad
    vc.calle = calle
    vc.codigo_postal = cp
    guardar_cambios(f'Videoclub #{codigo} actualizado.')
    return redirect(url_for(ROUTE_VIDEOCLUBS))


# ==================== PELÍCULAS ====================
@app.route('/peliculas', methods=['GET', 'POST'])
@login_required
def gestionar_peliculas():
    if request.method == 'POST':
        if not current_user.es_admin:
            abort(403)

        try:
            nombre = request.form.get('nombre', '').strip()
            director = request.form.get('director', '').strip() or None
            fecha_estreno = parse_fecha(request.form.get('fecha_estreno', ''))
            precio = Decimal(request.form.get('precio_alquiler', ''))
            vc_codigo = int(request.form.get('videoclub_codigo', ''))

            if not nombre or precio < Decimal('0.00') or not db.session.get(Videoclub, vc_codigo):
                raise ValueError('Datos de película inválidos.')

            if existe_pelicula_en_sucursal(nombre, vc_codigo):
                flash(
                    f'Error: La película "{nombre}" ya existe en el Videoclub #{vc_codigo}. '
                    'Solo se permite repetir título en sucursales diferentes.',
                    FLASH_DANGER,
                )
                return redirect(url_for(ROUTE_PELICULAS))

            db.session.add(
                Pelicula(
                    nombre=nombre,
                    director=director,
                    fecha_estreno=fecha_estreno,
                    precio_alquiler=precio.quantize(Decimal('0.01')),
                    videoclub_codigo=vc_codigo,
                )
            )
            guardar_cambios('Película añadida al catálogo del videoclub.')
        except (ValueError, InvalidOperation):
            flash('Error: Verifique el precio, fecha de estreno y videoclub seleccionado.', FLASH_DANGER)
        return redirect(url_for(ROUTE_PELICULAS))

    return render_template(
        'peliculas.html',
        peliculas=Pelicula.query.order_by(Pelicula.codigo).all(),
        videoclubs=Videoclub.query.order_by(Videoclub.codigo).all(),
    )


@app.route('/peliculas/editar/<int:codigo>', methods=['POST'])
@admin_required
def editar_pelicula(codigo: int):
    pelicula = db.get_or_404(Pelicula, codigo)
    try:
        nombre = request.form.get('nombre', '').strip()
        director = request.form.get('director', '').strip() or None
        fecha_estreno = parse_fecha(request.form.get('fecha_estreno', ''))
        precio = Decimal(request.form.get('precio_alquiler', ''))
        vc_codigo = int(request.form.get('videoclub_codigo', ''))

        if not nombre or precio < Decimal('0.00') or not db.session.get(Videoclub, vc_codigo):
            raise ValueError('Datos inválidos.')

        if existe_pelicula_en_sucursal(nombre, vc_codigo, excluir_codigo=codigo):
            flash(
                f'Error: Ya existe otra película llamada "{nombre}" en el Videoclub #{vc_codigo}.',
                FLASH_DANGER,
            )
            return redirect(url_for(ROUTE_PELICULAS))

        pelicula.nombre = nombre
        pelicula.director = director
        pelicula.fecha_estreno = fecha_estreno
        pelicula.precio_alquiler = precio.quantize(Decimal('0.01'))
        pelicula.videoclub_codigo = vc_codigo
        guardar_cambios(f'Película #{codigo} actualizada.')
    except (ValueError, InvalidOperation):
        flash('Error: Datos inválidos al actualizar la película.', FLASH_DANGER)
    return redirect(url_for(ROUTE_PELICULAS))


# ==================== SOCIOS ====================
@app.route('/socios', methods=['GET', 'POST'])
@login_required
def gestionar_socios():
    if request.method == 'POST':
        if not current_user.es_admin:
            abort(403)

        try:
            nombre = request.form.get('nombre', '').strip()
            edad = int(request.form.get('edad', ''))
            vc_codigo = int(request.form.get('videoclub_codigo', ''))
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')

            if not nombre or edad <= 0 or not db.session.get(Videoclub, vc_codigo):
                raise ValueError('Datos de socio inválidos.')
            if not username or len(password) < MIN_PASSWORD_LEN:
                raise ValueError('Credenciales inválidas.')

            nuevo = Socio(nombre=nombre, edad=edad, videoclub_codigo=vc_codigo)
            db.session.add(nuevo)
            db.session.flush()

            usuario = Usuario(username=username, rol=ROL_SOCIO, socio_codigo=nuevo.codigo)
            usuario.set_password(password)
            db.session.add(usuario)
            guardar_cambios('Socio registrado en la cadena APPV.')
        except ValueError:
            flash('Error: Verifique datos personales, videoclub y credenciales (mín. 8 caracteres).', FLASH_DANGER)
        return redirect(url_for(ROUTE_SOCIOS))

    socios = (
        Socio.query.order_by(Socio.codigo).all()
        if current_user.es_admin
        else [db.get_or_404(Socio, current_user.socio_codigo)]
    )
    return render_template('socios.html', socios=socios, videoclubs=Videoclub.query.order_by(Videoclub.codigo).all())


@app.route('/socios/editar/<int:codigo>', methods=['POST'])
@login_required
def editar_socio(codigo: int):
    if not current_user.es_admin and current_user.socio_codigo != codigo:
        abort(403)

    socio = db.get_or_404(Socio, codigo)
    try:
        nombre = request.form.get('nombre', '').strip()
        edad = int(request.form.get('edad', ''))
        if not nombre or edad <= 0:
            raise ValueError('Datos inválidos.')

        socio.nombre = nombre
        socio.edad = edad
        guardar_cambios(f'Datos del socio #{codigo} actualizados.')
    except ValueError:
        flash('Error: El nombre es obligatorio y la edad debe ser un entero positivo.', FLASH_DANGER)
    return redirect(url_for(ROUTE_SOCIOS))


# ==================== ALQUILERES ====================
@app.route('/alquileres', methods=['GET', 'POST'])
@login_required
def gestionar_alquileres():
    if request.method == 'POST':
        try:
            peliculas_ids = [int(pid) for pid in request.form.getlist('peliculas_codigos')]
            if not peliculas_ids:
                flash('Error: Debe seleccionar al menos una película para el alquiler.', FLASH_DANGER)
                return redirect(url_for(ROUTE_ALQUILERES))

            socio_codigo = (
                int(request.form.get('socio_codigo', ''))
                if current_user.es_admin
                else current_user.socio_codigo
            )
            fecha_recogida = parse_fecha(request.form.get('fecha_recogida', ''))
            fecha_devolucion = parse_fecha(request.form.get('fecha_devolucion', ''))

            if not db.session.get(Socio, socio_codigo):
                raise ValueError('Socio no válido.')
            if fecha_devolucion <= fecha_recogida:
                flash('Error: La fecha de devolución debe ser posterior a la fecha de recogida.', FLASH_DANGER)
                return redirect(url_for(ROUTE_ALQUILERES))

            peliculas_objs = Pelicula.query.filter(Pelicula.codigo.in_(peliculas_ids)).all()
            if len(peliculas_objs) != len(set(peliculas_ids)):
                raise ValueError('Película inválida.')

            nuevo_alquiler = Alquiler(
                fecha_recogida=fecha_recogida,
                fecha_devolucion=fecha_devolucion,
                socio_codigo=socio_codigo,
            )
            nuevo_alquiler.peliculas.extend(peliculas_objs)
            db.session.add(nuevo_alquiler)
            guardar_cambios(
                f'Alquiler registrado ({len(peliculas_objs)} película/s). '
                f'Total a pagar: {nuevo_alquiler.total_pagar:.2f} €'
            )
        except ValueError:
            flash('Error: Verifique las fechas y selecciones introducidas.', FLASH_DANGER)
        return redirect(url_for(ROUTE_ALQUILERES))

    if current_user.es_admin:
        alquileres = Alquiler.query.order_by(Alquiler.codigo).all()
        socios = Socio.query.order_by(Socio.codigo).all()
    else:
        alquileres = Alquiler.query.filter_by(socio_codigo=current_user.socio_codigo).order_by(Alquiler.codigo).all()
        socios = [db.get_or_404(Socio, current_user.socio_codigo)]

    return render_template(
        'alquileres.html',
        alquileres=alquileres,
        socios=socios,
        peliculas=Pelicula.query.order_by(Pelicula.codigo).all(),
    )


@app.route('/alquileres/editar/<int:codigo>', methods=['POST'])
@login_required
def editar_alquiler(codigo: int):
    alquiler = db.get_or_404(Alquiler, codigo)
    if not current_user.es_admin and alquiler.socio_codigo != current_user.socio_codigo:
        abort(403)

    try:
        fecha_edicion_actual = date.today()
        nueva_fecha_devolucion = parse_fecha(request.form.get('fecha_devolucion', ''))

        if nueva_fecha_devolucion <= fecha_edicion_actual or nueva_fecha_devolucion <= alquiler.fecha_recogida:
            flash(
                f'Error: La nueva fecha de devolución debe ser posterior a hoy ({fecha_edicion_actual}) '
                f'y a la fecha de recogida ({alquiler.fecha_recogida}).',
                FLASH_DANGER,
            )
            return redirect(url_for(ROUTE_ALQUILERES))

        alquiler.fecha_devolucion = nueva_fecha_devolucion
        guardar_cambios(f'Fecha de devolución del alquiler #{codigo} actualizada.')
    except ValueError:
        flash('Error: Formato de fecha inválido.', FLASH_DANGER)
    return redirect(url_for(ROUTE_ALQUILERES))


# ==================== ADMINISTRADORES (SOLO ADMIN) ====================
@app.route('/administradores', methods=['GET', 'POST'])
@admin_required
def gestionar_administradores():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not nombre or not username or len(password) < MIN_PASSWORD_LEN:
            flash(f'Error: Nombre, usuario y contraseña (mín. {MIN_PASSWORD_LEN} car.) son obligatorios.', FLASH_DANGER)
            return redirect(url_for(ROUTE_ADMINISTRADORES))

        admin = Administrador(nombre=nombre)
        db.session.add(admin)
        db.session.flush()

        usuario = Usuario(username=username, rol=ROL_ADMIN, administrador_codigo=admin.codigo)
        usuario.set_password(password)
        db.session.add(usuario)
        guardar_cambios('Administrador registrado correctamente.')
        return redirect(url_for(ROUTE_ADMINISTRADORES))

    return render_template('administradores.html', administradores=Administrador.query.order_by(Administrador.codigo).all())


@app.route('/administradores/editar/<int:codigo>', methods=['POST'])
@admin_required
def editar_administrador(codigo: int):
    admin = db.get_or_404(Administrador, codigo)
    nombre = request.form.get('nombre', '').strip()
    if not nombre:
        flash('Error: El nombre no puede estar vacío.', FLASH_DANGER)
        return redirect(url_for(ROUTE_ADMINISTRADORES))

    admin.nombre = nombre
    guardar_cambios(f'Administrador #{codigo} actualizado.')
    return redirect(url_for(ROUTE_ADMINISTRADORES))


# ==================== ESTADÍSTICAS (SOLO ADMIN) ====================
@app.route('/estadisticas', methods=['GET', 'POST'])
@admin_required
def gestionar_estadisticas():
    if request.method == 'POST':
        try:
            socio_codigo = int(request.form.get('socio_codigo', ''))
            mes = int(request.form.get('mes_estudio', ''))
            anio = int(request.form.get('anio_estudio', ''))
            fecha_creacion = date.today()

            if mes not in MESES_NOMBRES or not (1990 <= anio <= 2100):
                raise ValueError('Mes o año fuera de rango.')
            if not db.session.get(Socio, socio_codigo):
                raise ValueError('Socio inexistente.')

            existente = Estadistica.query.filter_by(
                socio_codigo=socio_codigo,
                mes_estudio=mes,
                anio_estudio=anio,
            ).first()
            if existente:
                flash(
                    f'Error: Ya existe una estadística para este socio en {MESES_NOMBRES[mes]} de {anio}.',
                    FLASH_DANGER,
                )
                return redirect(url_for(ROUTE_ESTADISTICAS))

            alquileres_socio = Alquiler.query.filter_by(socio_codigo=socio_codigo).all()
            total_gastado = sum(
                (
                    alq.total_pagar
                    for alq in alquileres_socio
                    if alq.fecha_recogida.month == mes and alq.fecha_recogida.year == anio
                ),
                Decimal('0.00'),
            )

            nueva_est = Estadistica(
                fecha_creacion=fecha_creacion,
                mes_estudio=mes,
                anio_estudio=anio,
                total_gastado=total_gastado,
                socio_codigo=socio_codigo,
                administrador_codigo=current_user.administrador_codigo,
            )
            db.session.add(nueva_est)
            guardar_cambios(
                f'Estadística generada: {total_gastado:.2f} € gastados en {MESES_NOMBRES[mes]} de {anio}.'
            )
        except ValueError:
            flash('Error: Verifique los datos introducidos para la estadística.', FLASH_DANGER)
        return redirect(url_for(ROUTE_ESTADISTICAS))

    anios_disponibles = list(range(2020, date.today().year + 2))
    return render_template(
        'estadisticas.html',
        estadisticas=Estadistica.query.order_by(Estadistica.codigo).all(),
        socios=Socio.query.order_by(Socio.codigo).all(),
        meses=MESES_NOMBRES,
        anios=anios_disponibles,
        anio_actual=date.today().year,
    )


if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(host='127.0.0.1', port=5000, debug=debug_mode)
