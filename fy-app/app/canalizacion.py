"""Canalización: se integra la app de referencia "Canaliza" tal cual —con
todas sus funciones intactas (DRC, cableado de iluminación, exportación a
PDF multi-hoja)— en vez de reimplementarla. Acá no hay un modelo de datos
propio que mantener sincronizado: se guarda y se lee el proyecto exactamente
como lo produce la función `buildProjectData()` de esa app.

`web/canaliza.html` es el archivo real, con tres agregados mínimos y
puntuales para poder integrarlo (`window.canalizaExportar`,
`window.canalizaImportar`, y una bandera para saltear el diálogo de
autoguardado del navegador cuando corre integrado). El resto del archivo
—DRC, trazado de cableado, PDF— es el mismo que ya se usaba antes de esto.
"""
from __future__ import annotations

# tipo de circuito de esta app -> "kind" que espera Canaliza, y sus defaults
# (ver CIRCUIT_TYPES / WIRE_COLOR_MAP en canaliza.html)
KIND_DE_TIPO = {
    "IUG": "iluminacion", "IUE": "iluminacion",
    "TUG": "tomas", "TUE": "especial", "ACU": "especial", "OCE": "especial",
}
PALETA = ["#c2410c", "#1d4ed8", "#047857", "#7c3aed", "#b91c1c", "#0e7490", "#a16207", "#be185d"]


def leer_proyecto(obra: dict) -> dict | None:
    return obra.get("canalizacion")


def guardar_proyecto(obra: dict, datos: dict) -> None:
    obra["canalizacion"] = datos


def circuitos_para_canaliza(obra: dict) -> list[dict]:
    """Los circuitos ya armados en el módulo de Circuitos, traducidos a la
    forma que espera Canaliza — para no tener que redefinirlos ahí también.
    Sólo se usa para el primer arranque; una vez que el usuario guarda un
    proyecto de canalización, ese guardado manda."""
    salida = []
    for i, c in enumerate(obra.get("circuitos") or []):
        kind = KIND_DE_TIPO.get(c.get("tipo"), "especial")
        salida.append({
            "id": c["id"], "name": c.get("nombre") or c["id"],
            "kind": kind, "color": PALETA[i % len(PALETA)],
            "section": c.get("seccionMm2") or 1.5,
            "cables": 2 if kind == "iluminacion" else 3,
            "prot": c.get("proteccionA") or 10,
            "dash": False, "detail": "", "ctype": c.get("tipo") or "OTRO",
        })
    return salida
