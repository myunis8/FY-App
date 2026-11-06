"""Automatizaciones: circuitos de comando y potencia que no son parte de la
instalación común (hoy: bomba de agua con tanque y cisterna).

Cada automatización guarda sólo sus PARÁMETROS (obra["automatizaciones"]).
Todo lo demás -- lista de componentes, esquemas, cables, notas, avisos -- se
DERIVA de esos parámetros cada vez que se pide (`resultado()`), así nunca
queda desactualizado respecto de las reglas, y es explicable: cada elección
(calibre, contactor, sección de cable) sale de una tabla de este archivo,
visible y editable, y el informe dice qué supuestos usó.

Los esquemas se arman por composición (potencia + comando), no se dibujan uno
por variante: agregar una variante es prender/apagar bloques, no hacer un
dibujo nuevo. Se generan como SVG, que sirve igual para la pantalla y para el
PDF (ver pdf_automatizacion.py).

IMPORTANTE -- las TABLAS de selección de abajo son reglas de diseño de este
programa (simplificaciones), no normativa: hay que revisarlas antes de
usarlas en obra, y cada resultado distingue "requisito normativo" de "buena
práctica" y "decisión de diseño" (ver `criterio`).
"""
from __future__ import annotations
import math
import re
from xml.sax.saxutils import escape

RHO_COBRE = 0.018          # Ω·mm²/m, mismo valor que usa Verificaciones técnicas
HP_A_KW = 0.7457

# ------------------------------------------------------------------ catálogo
CATALOGO = {
    "bomba_agua": {
        "nombre": "Bomba de agua con tanque y cisterna",
        "descripcion": ("Comando de una bomba monofásica: arranque directo con contactor, "
                        "flotantes de tanque y cisterna, selector manual/automático, "
                        "protección del motor y señalización."),
        "sistema": "Monofásico",
        "params": [
            {"id": "nombre", "label": "Nombre", "tipo": "texto", "default": "Bomba de agua"},
            {"id": "potenciaHp", "label": "Potencia (HP)", "tipo": "numero", "default": 0.5,
             "min": 0.1, "max": 5, "paso": 0.05,
             "ayuda": "Sólo informativo; el cálculo usa la corriente de chapa."},
            {"id": "corrienteA", "label": "Corriente de chapa (A)", "tipo": "numero", "default": 2.4,
             "min": 0.3, "max": 25, "paso": 0.1,
             "ayuda": "La que dice la chapa de la bomba, monofásica 220 V."},
            {"id": "tensionComando", "label": "Tensión de comando", "tipo": "opciones", "default": "24",
             "opciones": [["24", "24 VAC (transformador de aislación)"], ["220", "220 V (directo de la red)"]]},
            {"id": "conCisterna", "label": "Con cisterna", "tipo": "bool", "default": True,
             "ayuda": "Agrega la protección contra marcha en seco."},
            {"id": "proteccionCisterna", "label": "Protección de cisterna", "tipo": "opciones",
             "default": "flotante", "mostrarSi": "conCisterna",
             "opciones": [["flotante", "Flotante de 3 cables"], ["electrodos", "Relé de nivel por electrodos"]]},
            {"id": "selector", "label": "Selector Manual / 0 / Automático", "tipo": "bool", "default": True,
             "ayuda": "Sin selector la bomba sólo funciona en automático."},
            {"id": "senalizacion", "label": "Pilotos de señalización", "tipo": "bool", "default": True,
             "ayuda": "Marcha, falla del térmico y (con cisterna) falta de agua."},
            {"id": "proteccionMotor", "label": "Protección del motor", "tipo": "opciones", "default": "termico",
             "opciones": [["termico", "Relé térmico"], ["guardamotor", "Guardamotor"]]},
            {"id": "distanciaBombaM", "label": "Tablero a bomba (m)", "tipo": "numero", "default": 5,
             "min": 0.5, "max": 200, "paso": 0.5},
            {"id": "distanciaTanqueM", "label": "Tablero a flotante del tanque (m)", "tipo": "numero",
             "default": 13, "min": 1, "max": 200, "paso": 0.5,
             "ayuda": "Cable real: sumá la altura y la distancia horizontal."},
            {"id": "distanciaCisternaM", "label": "Tablero a flotante de cisterna (m)", "tipo": "numero",
             "default": 2.5, "min": 0.5, "max": 200, "paso": 0.5, "mostrarSi": "conCisterna"},
        ],
    },
}


def defaults(tipo: str) -> dict:
    return {p["id"]: p["default"] for p in CATALOGO[tipo]["params"]}


def normalizar_params(tipo: str, params: dict | None) -> dict:
    """Completa con los valores por defecto lo que falte y fuerza los tipos --
    una automatización guardada con una versión vieja (menos parámetros) sigue
    andando; nunca se descarta un parámetro desconocido."""
    base = defaults(tipo)
    out = dict(params or {})
    for p in CATALOGO[tipo]["params"]:
        v = out.get(p["id"], p["default"])
        if p["tipo"] == "numero":
            try:
                v = float(v)
            except (TypeError, ValueError):
                v = float(p["default"])
            v = max(p.get("min", v), min(p.get("max", v), v))
        elif p["tipo"] == "bool":
            v = bool(v)
        elif p["tipo"] == "opciones":
            if str(v) not in [o[0] for o in p["opciones"]]:
                v = base[p["id"]]
            v = str(v)
        out[p["id"]] = v
    return out


# --------------------------------------------------------------- tablas
# (corriente máx. del motor A, termomagnética bipolar A) -- la termomagnética
# protege el cable y es el seccionador general; el motor lo protege el térmico.
TABLA_TERMOMAGNETICA = [(3.0, 6), (6.0, 10), (9.0, 16), (14.0, 20), (18.0, 25)]
# (corriente máx. del motor A, contactor AC-3 en A, código sugerido bobina 24 V / 220 V)
TABLA_CONTACTOR = [(9, 9, "LC1E0910B7", "LC1E0910M7"), (12, 12, "LC1E1210B7", "LC1E1210M7"),
                   (18, 18, "LC1E1810B7", "LC1E1810M7"), (25, 25, "LC1E2510B7", "LC1E2510M7")]
# rangos de regulación del relé térmico: (mín A, máx A, código sugerido)
TABLA_TERMICO = [(0.63, 1.0, "LRE05"), (1.0, 1.6, "LRE06"), (1.6, 2.5, "LRE07"), (2.5, 4.0, "LRE08"),
                 (4.0, 6.0, "LRE10"), (5.5, 8.0, "LRE12"), (7.0, 10.0, "LRE14"), (9.0, 13.0, "LRE16"),
                 (12.0, 18.0, "LRE21"), (17.0, 25.0, "LRE22")]
# (corriente máx. A, sección del cable de la bomba mm²) -- criterio simple de
# capacidad; la caída de tensión se verifica aparte
TABLA_SECCION_BOMBA = [(10, 1.5), (16, 2.5), (25, 4.0)]
SECCIONES_COMANDO = [0.75, 1.0, 1.5, 2.5, 4.0]
CAIDA_MAX_COMANDO_PCT = 5.0       # decisión de diseño de este programa
CAIDA_MAX_BOMBA_PCT = 3.0         # decisión de diseño de este programa
INRUSH_BOBINA_A = {"24": 3.0, "220": 0.35}   # supuesto: corriente de cierre de la bobina


def _primero(tabla, valor, clave=0):
    for fila in tabla:
        if valor <= fila[clave]:
            return fila
    return tabla[-1]


def calcular(p: dict) -> dict:
    """Todas las elecciones derivadas de los parámetros, con sus supuestos."""
    I = p["corrienteA"]
    c = {"corriente": I, "kw": round(p["potenciaHp"] * HP_A_KW, 2), "avisos": []}
    c["termomag_A"] = _primero(TABLA_TERMOMAGNETICA, I)[1]
    if I > TABLA_TERMOMAGNETICA[-1][0]:
        c["avisos"].append(("advertencia", f"La corriente de {I:g} A supera lo previsto por las tablas de este "
                            "módulo (hasta 18 A): revisá a mano la protección y el contactor."))
    cont = _primero(TABLA_CONTACTOR, I)
    c["contactor_A"], c["contactor_cod"] = cont[1], cont[2] if p["tensionComando"] == "24" else cont[3]
    ter = next((t for t in TABLA_TERMICO if t[0] <= I <= t[1]), TABLA_TERMICO[-1])
    c["termico_rango"] = (ter[0], ter[1]); c["termico_cod"] = ter[2]
    c["dif_A"] = 25 if c["termomag_A"] <= 25 else 40
    c["seccion_bomba"] = _primero(TABLA_SECCION_BOMBA, I)[1]
    c["tension"] = int(p["tensionComando"])
    c["inrush"] = INRUSH_BOBINA_A[p["tensionComando"]]
    c["caida_bomba_pct"] = _caida(220, I, p["distanciaBombaM"], c["seccion_bomba"])

    def seccion_para(largo):
        for s in SECCIONES_COMANDO:
            if _caida(c["tension"], c["inrush"], largo, s) <= CAIDA_MAX_COMANDO_PCT:
                return s
        return SECCIONES_COMANDO[-1]
    c["seccion_tanque"] = seccion_para(p["distanciaTanqueM"])
    c["caida_tanque_pct"] = _caida(c["tension"], c["inrush"], p["distanciaTanqueM"], c["seccion_tanque"])
    if p["conCisterna"]:
        c["seccion_cisterna"] = max(1.0, seccion_para(p["distanciaCisternaM"]))
        c["caida_cisterna_pct"] = _caida(c["tension"], c["inrush"], p["distanciaCisternaM"], c["seccion_cisterna"])
    return c


def _caida(tension, corriente, largo, seccion):
    """ΔV% = 2·L·I·ρ / S / U · 100 (monofásico, ida y vuelta)."""
    return 2 * largo * corriente * RHO_COBRE / seccion / tension * 100


# ------------------------------------------------------------- componentes
def _comp(ref, nombre, espec, tipo, criterio, cant=1):
    return {"ref": ref, "nombre": nombre, "especificacion": espec, "tipo": tipo,
            "criterio": criterio, "cantidad": cant}


NORMATIVO = "Requisito normativo (verificar AEA 90364 vigente)"
BUENA = "Buena práctica"
DISENO = "Decisión de diseño"


def componentes(p: dict, c: dict) -> list[dict]:
    t24 = p["tensionComando"] == "24"
    out = [
        _comp("", "Gabinete estanco IP65", "Mínimo 250 x 300 x 170 mm, placa de montaje, puerta ciega, "
              "bornera de tierra.", "Obligatorio", DISENO),
        _comp("Q1", "Termomagnética bipolar", f"2x{c['termomag_A']} A curva C, 4,5 kA o más.",
              "Obligatorio", NORMATIVO),
        _comp("Q2", "Disyuntor diferencial", f"2x{c['dif_A']} A, 30 mA (clase AC o A).",
              "Obligatorio", NORMATIVO),
        _comp("K1", "Contactor", f"{c['contactor_A']} A AC-3, bobina {c['tension']} VAC, con 1 NA auxiliar "
              f"(13-14). Referencia sugerida: Schneider TeSys Easy {c['contactor_cod']} (verificar en catálogo).",
              "Obligatorio", DISENO),
    ]
    if p["proteccionMotor"] == "termico":
        out.append(_comp("F2", "Relé térmico",
                         f"Rango {c['termico_rango'][0]:g}-{c['termico_rango'][1]:g} A, ajustado a {c['corriente']:g} A. "
                         f"Contactos 95-96 (NC) y 97-98 (NA). Referencia sugerida: Schneider TeSys Easy "
                         f"{c['termico_cod']} (verificar en catálogo).", "Obligatorio", BUENA))
    else:
        out.append(_comp("F2", "Guardamotor",
                         f"Rango {c['termico_rango'][0]:g}-{c['termico_rango'][1]:g} A, ajustado a {c['corriente']:g} A. "
                         "Protege sobrecarga y cortocircuito y sirve de seccionador. Con contactos auxiliares "
                         "(NC y NA) para el comando y la luz de falla.", "Obligatorio", BUENA))
    if t24:
        out.append(_comp("T1", "Transformador 220/24 VAC", "50 VA, de aislación (no autotransformador), riel DIN.",
                         "Obligatorio", DISENO))
        out.append(_comp("F1", "Portafusible + fusible primario", "Fusible lento T1A, 5x20, riel DIN.",
                         "Obligatorio", DISENO))
    out.append(_comp("F3", "Portafusible + fusible de comando", "Fusible lento T2A, 5x20, riel DIN.",
                     "Obligatorio", DISENO))
    if p["selector"]:
        out.append(_comp("S1", "Selector 3 posiciones", "22 mm, posiciones fijas MAN-0-AUTO, 2 contactos NA.",
                         "Obligatorio", DISENO))
        out.append(_comp("S2", "Pulsador de parada", "22 mm, rojo, 1 NC.", "Obligatorio", DISENO))
        out.append(_comp("S3", "Pulsador de marcha", "22 mm, verde, 1 NA.", "Obligatorio", DISENO))
    out.append(_comp("B1", "Flotante de tanque", "Automático de tanque de 3 cables, cable del largo que haga falta.",
                     "Obligatorio", DISENO))
    if p["conCisterna"]:
        if p["proteccionCisterna"] == "flotante":
            out.append(_comp("B2", "Protección de cisterna (flotante)",
                             "Flotante de 3 cables: un contacto habilita la bomba si hay agua; el otro enciende "
                             "H3 si no hay.", "Obligatorio", BUENA))
        else:
            out.append(_comp("B2", "Protección de cisterna (relé de nivel por electrodos)",
                             "Kit relé + 3 electrodos, con contacto inversor (NA + NC) para el piloto H3.",
                             "Obligatorio", BUENA))
    if p["senalizacion"]:
        cant = 3 if p["conCisterna"] else 2
        det = "verde (en marcha), rojo (falla térmico)" + (" y ámbar (cisterna sin agua)" if p["conCisterna"] else "")
        out.append(_comp("H1 / H2" + (" / H3" if p["conCisterna"] else ""), "Pilotos LED",
                         f"22 mm, {c['tension']} V: {det}.", "Recomendado", BUENA, cant))
    cab = (f"3x{c['seccion_bomba']:g} mm² a la bomba (fase, neutro y tierra); "
           f"2x{c['seccion_tanque']:g} mm² al flotante del tanque ({p['distanciaTanqueM']:g} m)")
    if p["conCisterna"]:
        cab += f"; 4x{c['seccion_cisterna']:g} mm² al flotante de cisterna ({p['distanciaCisternaM']:g} m)"
    cab += "; cableado interno, borneras, prensacables, punteras y empalmes estancos."
    out.append(_comp("", "Cables y accesorios", cab, "Obligatorio", DISENO))
    return out


# ------------------------------------------------------------ explicaciones
def funcionamiento(p: dict) -> list[dict]:
    f = []
    cist = p["conCisterna"]
    if p["selector"]:
        f.append({"t": "Automático", "d": "La bomba arranca cuando el flotante del tanque (B1) detecta nivel bajo"
                  + (" y la cisterna (B2) tiene agua. " if cist else ". ")
                  + "Para cuando el tanque se llena" + (" o la cisterna se vacía." if cist else ".")})
        f.append({"t": "Manual", "d": "Se ignoran los flotantes. Arranca con el pulsador verde (S3) y se mantiene sola "
                  "por el contacto auxiliar del contactor (autorretención). Sólo para con el pulsador rojo (S2), con "
                  "el selector en 0 o si dispara la protección del motor."})
        f.append({"t": "0", "d": "Todo apagado, para mantenimiento o limpieza de tanques."})
    else:
        f.append({"t": "Automático", "d": "La bomba arranca cuando el flotante del tanque (B1) detecta nivel bajo"
                  + (" y la cisterna (B2) tiene agua" if cist else "") + ", y para cuando el tanque se llena. "
                  "No hay modo manual: para apagarla hay que cortar Q1 o Q2."})
    if cist:
        f.append({"t": "Protección en seco",
                  "d": "B2 está en serie en la rama automática" + (": en manual la bomba no se corta por falta de "
                  "agua, y si la cisterna se vacía se enciende la luz ámbar y hay que apagarla a mano. "
                  "Una bomba periférica en seco se daña en pocos minutos: en manual no conviene dejarla sin "
                  "supervisión." if p["selector"] else ".")})
    f.append({"t": "Falla del motor", "d": "Si dispara la protección del motor (sobrecarga, rotor trabado, falta de agua "
              "prolongada), corta el comando" + (" y enciende la luz roja" if p["senalizacion"] else "")
              + ". Se rearma a mano en el propio equipo."})
    return f


def supuestos(p: dict, c: dict) -> list[str]:
    s = [f"Bomba monofásica 220 V de {p['potenciaHp']:g} HP (aprox. {c['kw']:g} kW), corriente de chapa "
         f"{c['corriente']:g} A. Arranque directo con contactor.",
         f"Circuito de comando en {c['tension']} " + ("VAC con transformador de aislación 220/24 V."
                                                      if c["tension"] == 24 else "V, directo de la red (sin transformador)."),
         f"Tablero junto a la bomba. Cable hasta el flotante del tanque: {p['distanciaTanqueM']:g} m"
         + (f"; hasta la cisterna: {p['distanciaCisternaM']:g} m." if p["conCisterna"] else "."),
         f"Se supone una corriente de cierre de la bobina de {c['inrush']:g} A al {c['tension']} V para verificar "
         f"la caída de tensión del comando (límite adoptado: {CAIDA_MAX_COMANDO_PCT:g} %, decisión de diseño).",
         "Las secciones, calibres y contactores salen de las tablas de selección del programa (simplificaciones "
         "de diseño, no normativa): revisarlas antes de ejecutar."]
    return s


def cables(p: dict, c: dict) -> list[dict]:
    out = [{"tramo": "Tablero a bomba (220 V)", "cable": f"3x{c['seccion_bomba']:g} mm² (fase, neutro y tierra)",
            "largo": f"{p['distanciaBombaM']:g} m",
            "resultado": f"Caída {c['caida_bomba_pct']:.1f} %" + (
                "" if c["caida_bomba_pct"] <= CAIDA_MAX_BOMBA_PCT else f" (supera {CAIDA_MAX_BOMBA_PCT:g} %: subí la sección)")},
           {"tramo": f"Tablero a flotante del tanque ({c['tension']} V)",
            "cable": f"2x{c['seccion_tanque']:g} mm², empalmado al cable del flotante fuera del agua",
            "largo": f"{p['distanciaTanqueM']:g} m",
            "resultado": f"Con la bobina cerrando ({c['inrush']:g} A) la caída es {c['caida_tanque_pct']:.1f} %"}]
    if p["conCisterna"]:
        out.append({"tramo": f"Tablero a flotante de cisterna ({c['tension']} V)",
                    "cable": f"4x{c['seccion_cisterna']:g} mm² (usa 3 conductores; el verde-amarillo no se usa para señal)"
                    if p["proteccionCisterna"] == "flotante" else f"3x{c['seccion_cisterna']:g} mm² a los electrodos",
                    "largo": f"{p['distanciaCisternaM']:g} m",
                    "resultado": f"Caída {c['caida_cisterna_pct']:.1f} %"})
    return out


def notas_conexion(p: dict, c: dict) -> list[str]:
    n = []
    n.append("Los automáticos de flotante tienen 3 cables (común, NA y NC). El mismo modelo sirve para tanque o "
             "cisterna: lo que cambia es qué par de cables se usa. Probarlo con un tester antes de conectar.")
    if p["conCisterna"] and p["proteccionCisterna"] == "flotante":
        n.append("Flotante de cisterna: el común va a X1 (después de F3), el contacto que cierra con agua va a la "
                 "rama automática y el que cierra sin agua va al piloto H3. En el esquema B2 aparece dos veces, "
                 "pero es un solo flotante.")
    if c["tension"] == 24:
        n.append("Conectar a tierra el borne X2 del secundario: si un cable de flotante toca masa, salta el fusible "
                 "F3 en vez de arrancar la bomba sola.")
    if p["proteccionMotor"] == "termico":
        n.append("Relé térmico con bomba monofásica: los tres polos del relé tienen que llevar corriente, si no "
                 "dispara por falta de fase. La fase pasa por dos polos y el neutro por el tercero, con un puente "
                 "de la salida 2/T1 del relé a la entrada 3/L2 del contactor (ver tabla de conexión).")
        n.append(f"Ajustar el dial del térmico a {c['corriente']:g} A, la corriente de chapa, no más.")
    else:
        n.append(f"Ajustar el guardamotor a {c['corriente']:g} A, la corriente de chapa, no más.")
    if p["selector"]:
        n.append("Al pasar de AUTO a MAN el selector atraviesa la posición 0, así que la bomba se detiene. "
                 "En manual siempre hay que pulsar marcha para arrancarla.")
    n.append("Conductor de protección (PE) a la carcasa de la bomba, al gabinete" +
             (" y al núcleo del transformador." if c["tension"] == 24 else "."))
    n.append("Los cables de 220 V y los de comando conviene llevarlos por canaletas o recorridos separados, "
             "y usar colores distintos para identificarlos.")
    return n


def conexion_potencia(p: dict, c: dict) -> list[list[str]]:
    """Tabla de conexión de potencia (desde, hasta, qué es) -- sólo con relé térmico,
    que es el caso que necesita el puente para no disparar por falta de fase."""
    if p["proteccionMotor"] != "termico":
        return []
    return [["Fase (salida de Q2)", "Contactor 1 / L1", "Entrada de la fase"],
            ["Relé 2 / T1", "Contactor 3 / L2", f"Puente: la fase vuelve a entrar por el segundo polo (cable "
             f"{max(2.5, c['seccion_bomba']):g} mm², color de fase, con punteras)"],
            ["Relé 4 / T2", "Bomba, fase", "Salida de la fase a la bomba"],
            ["Neutro (salida de Q2)", "Contactor 5 / L3", "Entrada del neutro"],
            ["Relé 6 / T3", "Bomba, neutro", "Salida del neutro a la bomba"],
            ["Relé 95 - 96", "En serie en la rama de la bobina", "Corta el comando si dispara"],
            ["Relé 97 - 98", "Piloto rojo H2" if p["senalizacion"] else "(sin uso)", "Señal de falla"],
            ["Contactor A1 / A2", "Rama de comando / X2", "Bobina del contactor"],
            ["Contactor 13 / 14", "En paralelo con el pulsador de marcha" if p["selector"] else "(sin uso)",
             "Autorretención del modo manual"]]


def pruebas(p: dict, c: dict) -> list[str]:
    r = ["Con Q1 abierto, verificar continuidad de la tierra entre la carcasa de la bomba, el gabinete y la jabalina.",
         "Energizar sólo el comando (sin la bomba conectada)" + (" y probar cada posición del selector y cada flotante a mano."
                                                               if p["selector"] else " y probar cada flotante a mano.")]
    if p["conCisterna"]:
        r.append("Simular cisterna vacía en automático: la bomba debe parar" +
                 (" y encenderse la luz ámbar." if p["senalizacion"] else ".") +
                 (" En manual: la bomba sigue andando." if p["selector"] else ""))
    r.append("Probar el diferencial con su botón de test.")
    r.append(f"Con la bomba andando, medir la corriente con pinza: tiene que dar {c['corriente']:g} A o menos.")
    return r


def avisos(p: dict, c: dict) -> list[dict]:
    a = [{"gravedad": g, "texto": t} for g, t in c["avisos"]]
    if not p["conCisterna"]:
        a.append({"gravedad": "advertencia", "texto": "Sin protección de cisterna: nada impide que la bomba "
                  "arranque en seco si la cisterna se vacía. Una bomba periférica en seco se daña en minutos."})
    if p["conCisterna"] and p["selector"]:
        a.append({"gravedad": "info", "texto": "En manual no hay protección en seco (así está pensado el circuito): "
                  "la luz ámbar avisa pero no corta."})
    if c["caida_bomba_pct"] > CAIDA_MAX_BOMBA_PCT:
        a.append({"gravedad": "advertencia", "texto": f"Caída de tensión del cable de la bomba: "
                  f"{c['caida_bomba_pct']:.1f} % (límite adoptado {CAIDA_MAX_BOMBA_PCT:g} %)."})
    if c["caida_tanque_pct"] > CAIDA_MAX_COMANDO_PCT:
        a.append({"gravedad": "advertencia", "texto": f"Caída de tensión hasta el flotante del tanque: "
                  f"{c['caida_tanque_pct']:.1f} %: el contactor podría vibrar. Usá más sección o 220 V de comando."})
    if p["selector"] and not p["senalizacion"] and p["conCisterna"]:
        a.append({"gravedad": "info", "texto": "Sin pilotos: en manual no hay aviso visual de falta de agua."})
    return a


# ===================================================================== SVG
TRAZO = "#33506e"
NAVY = "#16283f"
GRIS = "#5b6b7a"
FASE = "#8a5a2b"
NEUTRO = "#2b6ca3"
TIERRA = "#2f7d5c"
ROJO = "#b3432f"
AMBAR = "#b8791a"
VERDE = "#2a7d4b"
FUENTE = "Helvetica, Arial, sans-serif"


class Svg:
    def __init__(self, w, h):
        self.w, self.h, self.p = w, h, []

    def line(self, x1, y1, x2, y2, c=TRAZO, w=1.1):
        self.p.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{c}" '
                      f'stroke-width="{w}" stroke-linecap="round"/>')

    def poly(self, pts, c=TRAZO, w=1.1, fill="none"):
        d = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        self.p.append(f'<polyline points="{d}" fill="{fill}" stroke="{c}" stroke-width="{w}" '
                      'stroke-linejoin="round" stroke-linecap="round"/>')

    def rect(self, x, y, w, h, c=TRAZO, fill="#ffffff", sw=1.1, rx=0):
        self.p.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" '
                      f'fill="{fill}" stroke="{c}" stroke-width="{sw}"/>')

    def circle(self, cx, cy, r, c=TRAZO, fill="none", sw=1.1):
        self.p.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{fill}" stroke="{c}" stroke-width="{sw}"/>')

    def dot(self, x, y, c=TRAZO, r=2.4):
        self.p.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{c}"/>')

    def text(self, x, y, s, size=8, fill=TRAZO, bold=False, anchor="start"):
        self.p.append(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FUENTE}" font-size="{size}" '
                      f'font-weight="{"700" if bold else "400"}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')

    def render(self):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w:.0f} {self.h:.0f}" '
                f'width="{self.w:.0f}" height="{self.h:.0f}">'
                f'<rect width="{self.w:.0f}" height="{self.h:.0f}" fill="#ffffff"/>' + "".join(self.p) + "</svg>")


# --- símbolos de comando (flujo horizontal; (x, y) = terminal izquierdo)
def _contacto(s, x, y, w=52, nc=False, pulsador=False, col=TRAZO):
    a, b = x + w * 0.28, x + w * 0.72
    s.line(x, y, a, y, col); s.line(b, y, x + w, y, col)
    s.line(a, y, b, y - 9, col)
    s.dot(a, y, col, 1.6); s.dot(b, y, col, 1.6)
    if nc:
        s.line(b, y - 9, b + 3, y - 12, col)     # gancho del NC
        s.line(b - 6, y - 4.5, b + 4, y - 4.5, col, 0.9)
    if pulsador:
        mx = (a + b) / 2
        s.line(mx, y - 4.5, mx, y - 16, col); s.line(mx - 5, y - 16, mx + 5, y - 16, col)


def _fusible_h(s, x, y, w=26):
    s.line(x, y, x + w, y); s.rect(x + 3, y - 4, w - 6, 8)
    s.line(x + 3, y, x + w - 3, y, TRAZO, 0.8)


def _fusible_v(s, x, y, h=26):
    s.line(x, y, x, y + h); s.rect(x - 4, y + 3, 8, h - 6)
    s.line(x, y + 3, x, y + h - 3, TRAZO, 0.8)


def _bobina(s, x, y, w=32):
    s.line(x, y, x + w, y); s.rect(x + 2, y - 8, w - 4, 16, fill="#ffffff")


def _lampara(s, cx, y, col, soft):
    s.circle(cx, y, 9, col, soft, 1.2)
    s.line(cx - 6, y - 6, cx + 6, y + 6, col, 1); s.line(cx - 6, y + 6, cx + 6, y - 6, col, 1)


def _etiq(s, cx, y, ref, desc="", col=NAVY, up=24):
    s.text(cx, y - up, ref, 7.6, col, True, "middle")
    if desc:
        s.text(cx, y + 18, desc, 6.2, GRIS, False, "middle")


def esquema_comando(p: dict, c: dict) -> str:
    """Circuito de comando en escalera: rama automática, rama manual con
    autorretención, común (térmico + bobina) y señalización."""
    XL, XR, XJ = 56, 736, 470            # riel izquierdo, derecho, nudo común
    t24 = c["tension"] == 24
    cist, sel, sen = p["conCisterna"], p["selector"], p["senalizacion"]
    ref_b2 = "B2 cisterna" if p["proteccionCisterna"] == "flotante" else "B2 relé nivel"
    s = Svg(800, 400)
    y = 118
    yA = y
    # ---- ramas
    rama_a = []
    if cist:
        rama_a.append(dict(ref=ref_b2, desc="cierra si HAY agua", kind="c"))
    if sel:
        rama_a.append(dict(ref="S1 AUTO", desc="", kind="c"))
    rama_a.append(dict(ref="B1 flotante tanque", desc="cierra con nivel bajo", kind="c"))
    pos_a = _fila(s, yA, XL, XJ, rama_a)
    yM = ySeal = None
    if sel:
        yM = yA + 78
        rama_m = [dict(ref="S1 MAN", desc="", kind="c"),
                  dict(ref="S2 PARADA", desc="pulsador NC", kind="p", nc=True, col=ROJO),
                  dict(ref="S3 MARCHA", desc="pulsador NA", kind="p", col=VERDE)]
        pos_m = _fila(s, yM, XL, XJ, rama_m)
        xs = (pos_m[1] + pos_m[2]) / 2                    # nudo entre S2 y S3
        ySeal = yM + 56
        s.dot(xs, yM)
        s.line(xs, yM, xs, ySeal)
        s.line(xs, ySeal, (xs + XJ) / 2 - 26, ySeal)
        _contacto(s, (xs + XJ) / 2 - 26, ySeal)
        s.line((xs + XJ) / 2 + 26, ySeal, XJ, ySeal)
        _etiq(s, (xs + XJ) / 2, ySeal, "K1 13-14 (autorretención)", "", NAVY, 18)
        s.line(XJ, ySeal, XJ, yA)
        s.dot(XJ, yM)
        s.dot(XJ, yA)
    # ---- común: F2 95-96 + bobina (+ H1)
    xf2 = XJ + 78
    n2 = XJ + 150
    _contacto(s, xf2 - 26, yA, nc=True)
    s.line(XJ, yA, xf2 - 26, yA); s.line(xf2 + 26, yA, n2, yA)
    _etiq(s, xf2, yA, "F2 95-96", "térmico (NC)" if p["proteccionMotor"] == "termico" else "aux. (NC)")
    s.dot(n2, yA)
    xb = n2 + 34
    s.line(n2, yA, xb, yA); _bobina(s, xb, yA); s.line(xb + 32, yA, XR, yA); s.dot(XR, yA)
    s.text(xb + 16, yA - 16, "K1", 7.6, NAVY, True, "middle")
    s.text(xb + 16, yA - 28, "bobina contactor", 6.2, GRIS, False, "middle")
    yLast = yA
    if sen:
        yH1 = yA + 52
        s.line(n2, yA, n2, yH1); s.line(n2, yH1, xb + 16 - 9, yH1)
        _lampara(s, xb + 16, yH1, VERDE, "#d6efdf"); s.line(xb + 16 + 9, yH1, XR, yH1); s.dot(XR, yH1)
        s.text(xb + 16, yH1 + 22, "H1 verde: en marcha", 6.6, VERDE, True, "middle")
    # ---- señalización de falla y falta de agua
    y = (ySeal if sel else yA) + 66
    if sen:
        _fila_senal(s, y, XL, XR, [dict(ref="F2 97-98", desc="térmico (NA)" if p["proteccionMotor"] == "termico"
                                        else "aux. (NA)", kind="c")], "H2 rojo: falla térmico", ROJO, "#f6d9d4")
        yLast = y
        if cist:
            y += 66
            _fila_senal(s, y, XL, XR, [dict(ref=ref_b2 + " (NC)", desc="mismo " + (
                "flotante, 3er cable" if p["proteccionCisterna"] == "flotante" else "relé, contacto inversor")
                + ": cierra SIN agua", kind="c", nc=True)], "H3 ámbar: sin agua", AMBAR, "#f6e6c6")
            yLast = y
    # ---- rieles
    yFin = yLast + 34
    col_x1 = NEUTRO if t24 else FASE
    s.line(XL, 36, XL, yFin, col_x1, 1.6)
    s.line(XR, 36, XR, yFin, NEUTRO, 1.6)
    # fusible F3 en el riel izquierdo
    _fusible_v(s, XL, 50, 28)
    s.text(XL + 10, 66, "F3 fusible 2 A", 6.8, NAVY, True)
    s.text(XL, 26, "X1 (24 VAC)" if t24 else "L (220 V)", 7.8, NEUTRO if t24 else FASE, True, "middle")
    s.text(XR, 26, "X2 (0 V)" if t24 else "N", 7.8, NEUTRO, True, "middle")
    if t24:
        s.dot(XR, 50, TIERRA)
        s.line(XR, 50, XR + 16, 50, TIERRA, 1.1)
        s.line(XR + 16, 50, XR + 16, 54, TIERRA, 1.1)
        for k, ww in enumerate((12, 8, 4)):
            s.line(XR + 16 - ww / 2, 54 + k * 3, XR + 16 + ww / 2, 54 + k * 3, TIERRA, 1)
        s.text(XR + 16, 72, "a tierra", 6.2, TIERRA, False, "middle")
    if sel:
        s.text(XL + 8, yFin - 2, "S1 = selector MAN - 0 - AUTO (en 0 ambas ramas quedan abiertas)", 6.4, GRIS)
    s.h = yFin + 8
    return s.render()


def _fila(s, y, x0, x1, items):
    """Dibuja los elementos repartidos entre x0 y x1; devuelve los centros."""
    n = len(items)
    cen = [x0 + (i + 1) * (x1 - x0) / (n + 1) for i in range(n)]
    x = x0
    for it, cx in zip(items, cen):
        w = 52
        s.line(x, y, cx - w / 2, y)
        _contacto(s, cx - w / 2, y, w, nc=it.get("nc", False), pulsador=it.get("kind") == "p",
                  col=it.get("col", TRAZO))
        _etiq(s, cx, y, it["ref"], it.get("desc", ""), it.get("col", NAVY),
              up=30 if it.get("kind") == "p" else 24)
        x = cx + w / 2
    s.line(x, y, x1, y)
    s.dot(x0, y)
    return cen


def _fila_senal(s, y, x0, xr, items, texto, col, soft):
    cen = _fila(s, y, x0, 470, items)
    xl = 640
    s.line(470, y, xl - 9, y); _lampara(s, xl, y, col, soft); s.line(xl + 9, y, xr, y); s.dot(xr, y)
    s.text(xl, y + 22, texto, 6.6, col, True, "middle")


def esquema_potencia(p: dict, c: dict) -> str:
    """Circuito de potencia: L y N pasan por Q1, Q2, K1 y el elemento de
    protección del motor hasta la bomba; PE va aparte. Con comando en 24 V se
    deriva la alimentación del transformador después de Q2."""
    s = Svg(800, 300)
    yL, yN, yPE = 130, 190, 262
    x0 = 70
    t24 = c["tension"] == 24
    xq1, xq2, xnodo, xk1, xf2, xm = 150, 270, 360, 490, 580, 700
    s.text(x0 - 14, yL + 4, "L", 9, FASE, True, "end"); s.text(x0 - 14, yN + 4, "N", 9, NEUTRO, True, "end")
    s.text(x0 - 14, yPE + 4, "PE", 9, TIERRA, True, "end")
    s.text(x0 - 6, yL - 12, "220 V", 6.4, GRIS, False, "end")
    for yy, col in ((yL, FASE), (yN, NEUTRO)):
        s.line(x0, yy, xq1 - 18, yy, col, 1.6)
        for xx in (xq1, xq2, xk1):
            _contacto(s, xx - 18, yy, 36, col=col)
        s.line(xq1 + 18, yy, xq2 - 18, yy, col, 1.6)
        s.line(xq2 + 18, yy, xk1 - 18, yy, col, 1.6)
        s.line(xk1 + 18, yy, xf2 - 14, yy, col, 1.6)
        s.rect(xf2 - 14, yy - 7, 28, 14)
        s.poly([(xf2 - 10, yy), (xf2 - 6, yy), (xf2 - 6, yy - 4), (xf2 + 2, yy - 4), (xf2 + 2, yy + 4),
                (xf2 + 6, yy + 4), (xf2 + 6, yy), (xf2 + 10, yy)], TRAZO, 0.9)
        s.line(xf2 + 14, yy, xm, yy, col, 1.6)
    for xx in (xq1, xq2, xk1, xf2):                    # unión mecánica entre los dos polos
        s.line(xx, yL + (3 if xx != xf2 else 8), xx, yN - (3 if xx != xf2 else 8), "#9aa9b8", 0.9)
    s.rect(xq2 - 26, yL - 22, 52, yN - yL + 44, "#9aa9b8", "none", 0.9)      # diferencial: recuadro
    # motor
    cym = (yL + yN) / 2
    s.line(xm, yL, xm, cym - 24, FASE, 1.6); s.line(xm, yN, xm, cym + 24, NEUTRO, 1.6)
    s.circle(xm, cym, 24, TRAZO, "#eef2f6", 1.3)
    s.text(xm, cym + 2, "M", 11, NAVY, True, "middle"); s.text(xm, cym + 14, "1~", 7, GRIS, False, "middle")
    s.text(xm + 32, cym + 3, "Bomba", 7.6, NAVY, True)
    # tierra
    s.line(x0, yPE, xm, yPE, TIERRA, 1.6)
    s.line(xm + 14, yPE, xm + 14, cym + 19.5, TIERRA, 1.2)      # PE a la carcasa, aparte del neutro
    s.dot(xm + 14, yPE, TIERRA)
    s.text(380, yPE + 18, "Conductor de protección (PE) a carcasa de la bomba y gabinete"
           + (" y núcleo del transformador" if t24 else ""), 6.6, TIERRA, False, "middle")
    # derivación al comando (después del diferencial)
    s.dot(xnodo, yL, FASE); s.dot(xnodo + 24, yN, NEUTRO)
    if t24:
        s.line(xnodo, yL, xnodo, 64, FASE, 1.4); _fusible_h(s, xnodo, 64, 28)
        s.line(xnodo + 28, 64, 430, 64, FASE, 1.4); s.line(430, 64, 430, 70, FASE, 1.4)
        s.line(xnodo + 24, yN, xnodo + 24, 100, NEUTRO, 1.4); _fusible_h(s, xnodo + 24, 100, 28)
        s.line(xnodo + 52, 100, 430, 100, NEUTRO, 1.4); s.line(430, 100, 430, 94, NEUTRO, 1.4)
        s.circle(430, 82, 12, TRAZO, "#ffffff"); s.circle(448, 82, 12, TRAZO, "#ffffff")
        s.line(460, 78, 520, 78, NEUTRO, 1.2); s.line(460, 86, 520, 86, NEUTRO, 1.2)
        s.text(526, 81, "X1", 6.8, NEUTRO, True); s.text(526, 91, "X2", 6.8, NEUTRO, True)
        s.text(552, 86, "a circuito de comando 24 VAC", 6.4, NEUTRO)
        s.text(439, 50, "T1  220/24 VAC 50 VA", 7, NAVY, True, "middle")
        s.text(xnodo + 14, 56, "F1 (1 A)", 6.2, GRIS, False, "middle")
    else:
        s.line(xnodo, yL, xnodo, 84, FASE, 1.4); s.line(xnodo + 24, yN, xnodo + 24, 84, NEUTRO, 1.4)
        s.circle(xnodo, 84, 2.6, FASE, "#ffffff"); s.circle(xnodo + 24, 84, 2.6, NEUTRO, "#ffffff")
        s.text(xnodo + 36, 80, "L y N a circuito de comando 220 V (por F3)", 6.4, GRIS)
    # rótulos: referencia arriba de L, descripción abajo de N (no pisan la unión mecánica)
    for xx, ref, desc, dy in ((xq1, "Q1", f"Termomag. 2x{c['termomag_A']} A C", 20),
                              (xq2, "Q2", "Diferencial 30 mA", 36),
                              (xk1, "K1", f"Contactor {c['contactor_A']} A", 20),
                              (xf2, "F2", "Guardamotor" if p["proteccionMotor"] == "guardamotor" else "Relé térmico", 20)):
        s.text(xx, yL - (30 if ref == "Q2" else 22), ref, 7.6, NAVY, True, "middle")
        s.text(xx, yN + dy, desc, 6.2, GRIS, False, "middle")
    s.h = 296
    return s.render()


# ===================================================================== API
def _coma(x):
    """Decimales con coma en todos los textos que ve el usuario (2.4 -> 2,4)."""
    if isinstance(x, str):
        return re.sub(r"(?<=\d)\.(?=\d)", ",", x)
    if isinstance(x, list):
        return [_coma(i) for i in x]
    if isinstance(x, dict):
        return {k: _coma(v) for k, v in x.items()}
    return x


def resultado(auto: dict) -> dict:
    """Todo lo derivado de una automatización: lo que muestran la pantalla y el PDF."""
    tipo = auto.get("tipo", "bomba_agua")
    if tipo not in CATALOGO:
        return {"error": f"Tipo de automatización desconocido: {tipo}"}
    p = normalizar_params(tipo, auto.get("params"))
    c = calcular(p)
    textos = _coma({
        "supuestos": supuestos(p, c),
        "funcionamiento": funcionamiento(p),
        "componentes": componentes(p, c),
        "cables": cables(p, c),
        "conexionPotencia": conexion_potencia(p, c),
        "notas": notas_conexion(p, c),
        "pruebas": pruebas(p, c),
        "avisos": avisos(p, c),
    })
    return {
        "tipo": tipo, "titulo": CATALOGO[tipo]["nombre"], "nombre": p["nombre"],
        "sistema": CATALOGO[tipo]["sistema"],
        "params": p,
        **textos,
        "calculo": {k: v for k, v in c.items() if k != "avisos"},
        "svg": {"potencia": esquema_potencia(p, c), "comando": esquema_comando(p, c)},
    }


def nueva(tipo: str = "bomba_agua") -> dict:
    import time
    return {"id": f"auto_{int(time.time() * 1000):x}", "tipo": tipo,
            "params": defaults(tipo)}
