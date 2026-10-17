"""Punto de entrada para ``python -m orakulue``.

Se mantiene el nombre ``__main__`` porque es el que exige Python para ejecutar
un paquete como programa.
"""

import sys

from orakulue.interfaz.linea_ordenes import principal

sys.exit(principal())
