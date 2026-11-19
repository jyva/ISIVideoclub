from datetime import date
from decimal import Decimal

from app import app, inicializar_admin_por_defecto
from models import (
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


def poblar_datos_iniciales() -> None:
    with app.app_context():
        db.create_all()
        inicializar_admin_por_defecto()

        if Videoclub.query.count() > 0:
            print("La base de datos ya contiene registros iniciales. No se realizaron duplicados.")
            return

        # 1. Segundo Administrador
        admin_sec = Administrador(nombre="Laura Martínez (Supervisora)")
        db.session.add(admin_sec)
        db.session.flush()

        user_admin_sec = Usuario(
            username="laura_admin",
            rol=ROL_ADMIN,
            administrador_codigo=admin_sec.codigo,
        )
        user_admin_sec.set_password("AdminLaura2026!")
        db.session.add(user_admin_sec)

        # 2. Videoclubs de la cadena APPV
        vc_valencia = Videoclub(
            nombre_gerente="Carlos Navarro",
            ciudad="València",
            calle="Calle Colón 42",
            codigo_postal="46004",
        )
        vc_madrid = Videoclub(
            nombre_gerente="Elena Gómez",
            ciudad="Madrid",
            calle="Calle Gran Vía 28",
            codigo_postal="28013",
        )
        vc_barcelona = Videoclub(
            nombre_gerente="Marc Puig",
            ciudad="Barcelona",
            calle="Rambla de Catalunya 15",
            codigo_postal="08007",
        )
        db.session.add_all([vc_valencia, vc_madrid, vc_barcelona])
        db.session.flush()

        # 3. Catálogo de Películas (incluye mismo título en distintos videoclubs con código propio)
        peliculas = [
            Pelicula(
                nombre="Inception",
                director="Christopher Nolan",
                fecha_estreno=date(2010, 7, 16),
                precio_alquiler=Decimal("3.50"),
                videoclub_codigo=vc_valencia.codigo,
            ),
            Pelicula(
                nombre="Inception",
                director="Christopher Nolan",
                fecha_estreno=date(2010, 7, 16),
                precio_alquiler=Decimal("3.75"),
                videoclub_codigo=vc_madrid.codigo,
            ),
            Pelicula(
                nombre="Interstellar",
                director="Christopher Nolan",
                fecha_estreno=date(2014, 11, 7),
                precio_alquiler=Decimal("4.00"),
                videoclub_codigo=vc_valencia.codigo,
            ),
            Pelicula(
                nombre="El Padrino",
                director="Francis Ford Coppola",
                fecha_estreno=date(1972, 3, 24),
                precio_alquiler=Decimal("3.00"),
                videoclub_codigo=vc_madrid.codigo,
            ),
            Pelicula(
                nombre="Pulp Fiction",
                director="Quentin Tarantino",
                fecha_estreno=date(1994, 10, 14),
                precio_alquiler=Decimal("3.25"),
                videoclub_codigo=vc_barcelona.codigo,
            ),
            Pelicula(
                nombre="Dune: Parte Dos",
                director="Denis Villeneuve",
                fecha_estreno=date(2024, 3, 1),
                precio_alquiler=Decimal("4.50"),
                videoclub_codigo=vc_barcelona.codigo,
            ),
            Pelicula(
                nombre="Blade Runner 2049",
                director=None,
                fecha_estreno=date(2017, 10, 6),
                precio_alquiler=Decimal("3.50"),
                videoclub_codigo=vc_valencia.codigo,
            ),
        ]
        db.session.add_all(peliculas)
        db.session.flush()

        # 4. Socios y sus credenciales de acceso
        socio_ana = Socio(nombre="AnaBelén Torres", edad=29, videoclub_codigo=vc_valencia.codigo)
        socio_javier = Socio(nombre="Javier Ruiz", edad=34, videoclub_codigo=vc_madrid.codigo)
        socio_sofia = Socio(nombre="Sofía Ferrer", edad=22, videoclub_codigo=vc_barcelona.codigo)
        db.session.add_all([socio_ana, socio_javier, socio_sofia])
        db.session.flush()

        usuarios_socios = [
            ("ana_torres", "SocioAna2026!", socio_ana.codigo),
            ("javier_ruiz", "SocioJavier2026!", socio_javier.codigo),
            ("sofia_ferrer", "SocioSofia2026!", socio_sofia.codigo),
        ]
        for uname, pwd, scod in usuarios_socios:
            u = Usuario(username=uname, rol=ROL_SOCIO, socio_codigo=scod)
            u.set_password(pwd)
            db.session.add(u)

        # 5. Alquileres (multivideoclub y con múltiples películas por alquiler)
        alq_1 = Alquiler(
            fecha_recogida=date(2026, 10, 5),
            fecha_devolucion=date(2026, 10, 9),
            socio_codigo=socio_ana.codigo,
        )
        alq_1.peliculas.extend([peliculas[0], peliculas[3]])  # 3.50 + 3.00 = 6.50 €

        alq_2 = Alquiler(
            fecha_recogida=date(2026, 10, 18),
            fecha_devolucion=date(2026, 10, 22),
            socio_codigo=socio_ana.codigo,
        )
        alq_2.peliculas.extend([peliculas[5]])  # 4.50 € (Total Octubre Ana = 11.00 €)

        alq_3 = Alquiler(
            fecha_recogida=date(2026, 11, 2),
            fecha_devolucion=date(2026, 11, 6),
            socio_codigo=socio_javier.codigo,
        )
        alq_3.peliculas.extend([peliculas[1], peliculas[2], peliculas[4]])  # 3.75 + 4.00 + 3.25 = 11.00 €

        alq_4 = Alquiler(
            fecha_recogida=date(2026, 11, 10),
            fecha_devolucion=date(2026, 11, 14),
            socio_codigo=socio_sofia.codigo,
        )
        alq_4.peliculas.extend([peliculas[6]])  # 3.50 €

        db.session.add_all([alq_1, alq_2, alq_3, alq_4])
        db.session.flush()

        # 6. Estadística Mensual ya calculada (Octubre 2026 para Ana)
        est_ana_oct = Estadistica(
            fecha_creacion=date(2026, 11, 1),
            mes_estudio=10,
            anio_estudio=2026,
            total_gastado=alq_1.total_pagar + alq_2.total_pagar,
            socio_codigo=socio_ana.codigo,
            administrador_codigo=admin_sec.codigo,
        )
        db.session.add(est_ana_oct)

        db.session.commit()
        print("Datos iniciales de APPV Videoclub cargados correctamente en PostgreSQL.")


if __name__ == "__main__":
    poblar_datos_iniciales()
