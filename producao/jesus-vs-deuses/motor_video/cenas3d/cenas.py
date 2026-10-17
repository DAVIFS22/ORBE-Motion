"""Registro de todas as cenas 3D (importar este módulo preenche `CENAS`)."""

import cenas_egito  # noqa: F401
from cenas_base import CENAS  # noqa: F401

try:
    import cenas_grecia_nordico  # noqa: F401
except ModuleNotFoundError:
    pass
try:
    import cenas_judeia  # noqa: F401
except ModuleNotFoundError:
    pass
try:
    import cenas_mapa_foto  # noqa: F401
except ModuleNotFoundError:
    pass
