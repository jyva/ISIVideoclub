from datetime import date
from decimal import Decimal
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

MAX_LEN_NOMBRE = 100
MAX_LEN_TITULO = 150
MAX_LEN_DIRECCION = 150
MAX_LEN_HASH = 256
LEN_CODIGO_POSTAL = 5

ROL_ADMIN = 'admin'
ROL_SOCIO = 'socio'

alquiler_pelicula = db.Table(
    'alquiler_pelicula',
    db.Column('alquiler_codigo', db.Integer, db.ForeignKey('alquiler.codigo'), primary_key=True),
    db.Column('pelicula_codigo', db.Integer, db.ForeignKey('pelicula.codigo'), primary_key=True),
)


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuario'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(MAX_LEN_NOMBRE), unique=True, nullable=False)
    password_hash = db.Column(db.String(MAX_LEN_HASH), nullable=False)
    rol = db.Column(db.String(20), nullable=False)

    socio_codigo = db.Column(db.Integer, db.ForeignKey('socio.codigo'), unique=True, nullable=True)
    administrador_codigo = db.Column(
        db.Integer, db.ForeignKey('administrador.codigo'), unique=True, nullable=True
    )

    socio = db.relationship('Socio', backref=db.backref('usuario', uselist=False))
    administrador = db.relationship('Administrador', backref=db.backref('usuario', uselist=False))

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def es_admin(self) -> bool:
        return self.rol == ROL_ADMIN

    @property
    def es_socio(self) -> bool:
        return self.rol == ROL_SOCIO


class Administrador(db.Model):
    __tablename__ = 'administrador'
    codigo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(MAX_LEN_NOMBRE), nullable=False)


class Videoclub(db.Model):
    __tablename__ = 'videoclub'
    codigo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_gerente = db.Column(db.String(MAX_LEN_NOMBRE), nullable=False)
    ciudad = db.Column(db.String(MAX_LEN_NOMBRE), nullable=False)
    calle = db.Column(db.String(MAX_LEN_DIRECCION), nullable=False)
    codigo_postal = db.Column(db.String(LEN_CODIGO_POSTAL), nullable=False)

    peliculas = db.relationship('Pelicula', backref='videoclub', lazy=True, cascade='all, delete-orphan')
    socios_registrados = db.relationship('Socio', backref='videoclub_registro', lazy=True)


class Pelicula(db.Model):
    __tablename__ = 'pelicula'
    codigo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(MAX_LEN_TITULO), nullable=False)
    director = db.Column(db.String(MAX_LEN_NOMBRE), nullable=True)
    fecha_estreno = db.Column(db.Date, nullable=False)
    precio_alquiler = db.Column(db.Numeric(10, 2), nullable=False)
    videoclub_codigo = db.Column(db.Integer, db.ForeignKey('videoclub.codigo'), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('nombre', 'videoclub_codigo', name='uix_pelicula_nombre_videoclub'),
    )


class Socio(db.Model):
    __tablename__ = 'socio'
    codigo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(MAX_LEN_NOMBRE), nullable=False)
    edad = db.Column(db.Integer, nullable=False)
    videoclub_codigo = db.Column(db.Integer, db.ForeignKey('videoclub.codigo'), nullable=False)

    alquileres = db.relationship('Alquiler', backref='socio', lazy=True)
    estadisticas = db.relationship('Estadistica', backref='socio', lazy=True)


class Alquiler(db.Model):
    __tablename__ = 'alquiler'
    codigo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha_recogida = db.Column(db.Date, nullable=False)
    fecha_devolucion = db.Column(db.Date, nullable=False)
    socio_codigo = db.Column(db.Integer, db.ForeignKey('socio.codigo'), nullable=False)

    peliculas = db.relationship(
        'Pelicula',
        secondary=alquiler_pelicula,
        lazy='subquery',
        backref=db.backref('alquileres', lazy=True),
    )

    @property
    def total_pagar(self) -> Decimal:
        return sum((Decimal(str(p.precio_alquiler)) for p in self.peliculas), Decimal('0.00'))


class Estadistica(db.Model):
    __tablename__ = 'estadistica'
    codigo = db.Column(db.Integer, primary_key=True, autoincrement=True)
    fecha_creacion = db.Column(db.Date, nullable=False)
    mes_estudio = db.Column(db.Integer, nullable=False)
    anio_estudio = db.Column(db.Integer, nullable=False)
    total_gastado = db.Column(db.Numeric(10, 2), nullable=False)

    socio_codigo = db.Column(db.Integer, db.ForeignKey('socio.codigo'), nullable=False)
    administrador_codigo = db.Column(db.Integer, db.ForeignKey('administrador.codigo'), nullable=False)
    administrador = db.relationship('Administrador', backref='estadisticas')

    __table_args__ = (
        db.UniqueConstraint('socio_codigo', 'mes_estudio', 'anio_estudio', name='uix_socio_mes_anio'),
    )
