"""Formato legible de tamaños, cifras y rutas para los informes."""

from pathlib import Path


class Formato:
    """Funciones de presentación agrupadas, sin estado."""

    @staticmethod
    def tamano(bytes_: int) -> str:
        """Expresa un tamaño en la unidad más cómoda, con coma decimal.

        Args:
            bytes_: tamaño en bytes.

        Returns:
            Texto como ``"1,4 GB"`` o ``"820 KB"``.
        """
        valor = float(bytes_)
        for unidad in ("B", "KB", "MB", "GB"):
            if valor < 1000 or unidad == "GB":
                if unidad == "B":
                    return f"{int(valor)} B"
                return f"{valor:.1f} {unidad}".replace(".", ",")
            valor /= 1000
        raise AssertionError("inalcanzable")

    @staticmethod
    def cifra(numero: int) -> str:
        """Escribe un entero con punto de millares, como en castellano.

        Args:
            numero: entero.

        Returns:
            Texto como ``"4.397"``.
        """
        return f"{numero:,}".replace(",", ".")

    @staticmethod
    def ruta(ruta: Path, personal: Path) -> str:
        """Abrevia una ruta con ``~`` si está dentro del directorio personal.

        Args:
            ruta: ruta absoluta.
            personal: directorio personal.

        Returns:
            Ruta abreviada como texto.
        """
        if ruta.is_relative_to(personal):
            relativa = ruta.relative_to(personal)
            return "~" if str(relativa) == "." else f"~/{relativa}"
        return str(ruta)

    @staticmethod
    def carpeta_resumida(ruta: Path, personal: Path, niveles: int) -> Path:
        """Recorta la carpeta de un fichero a sus primeros niveles bajo ``personal``.

        Sirve para agrupar: ``~/Documentos/formakuntza/errekurtsoak/Python/x.pdf``
        con tres niveles queda en ``~/Documentos/formakuntza/errekurtsoak``.

        Args:
            ruta: ruta absoluta de un fichero.
            personal: directorio personal.
            niveles: número de carpetas que se conservan.

        Returns:
            Carpeta recortada, absoluta.
        """
        carpeta = ruta.parent
        if not carpeta.is_relative_to(personal):
            return carpeta
        partes = carpeta.relative_to(personal).parts[:niveles]
        return personal.joinpath(*partes)
