"""
Dataset curado de casetas (plazas de cobro) de México con tarifas 2026.

Fuente de tarifas: CAPUFE — "Tarifas vigentes 2026"
(https://pot.capufe.mx/) + concesiones publicadas (Arco Norte, etc.).
Las coordenadas son la ubicación aproximada de cada plaza de cobro sobre la
autopista (precisión suficiente para emparejar una caseta detectada en la ruta
con su tarifa real, radio de match ~8 km).

Categorías de vehículo (clasificación CAPUFE):
  moto      Motocicleta
  auto      Automóvil / Pick-up
  autobus   Autobús
  camion2   Camión 2 ejes
  camion3   Camión 3 ejes
  camion4   Camión 4 ejes
  camion5   Camión 5 ejes
  camion6   Camión 6 ejes

Todas las tarifas en pesos mexicanos (MXN).
"""
from typing import Dict, List, Optional, Tuple
import math

VEHICLE_CLASSES = [
    {"key": "moto",    "label": "Motocicleta",   "axes": 2},
    {"key": "auto",    "label": "Automóvil",     "axes": 2},
    {"key": "autobus", "label": "Autobús",       "axes": 2},
    {"key": "camion2", "label": "Camión 2 ejes", "axes": 2},
    {"key": "camion3", "label": "Camión 3 ejes", "axes": 3},
    {"key": "camion4", "label": "Camión 4 ejes", "axes": 4},
    {"key": "camion5", "label": "Camión 5 ejes", "axes": 5},
    {"key": "camion6", "label": "Camión 6 ejes", "axes": 6},
]
VEHICLE_CLASS_KEYS = [v["key"] for v in VEHICLE_CLASSES]
DEFAULT_VEHICLE_CLASS = "auto"

# Cuando se detecta una caseta real (OSM) que NO está en el dataset, se estima
# su costo a partir de un promedio nacional por categoría (determinístico).
FALLBACK_AUTO_MXN = 95.0
FALLBACK_FACTORS = {
    "moto": 0.5, "auto": 1.0, "autobus": 1.95,
    "camion2": 1.95, "camion3": 2.6, "camion4": 3.3, "camion5": 4.5, "camion6": 5.2,
}

# Factor de consumo de combustible relativo al automóvil (base auto = 1.0).
# Moto consume mucho menos; autobús y camiones (diésel, mayor masa) consumen más,
# escalando con el número de ejes / carga.
FUEL_FACTORS = {
    "moto": 0.45, "auto": 1.0, "autobus": 3.0,
    "camion2": 2.6, "camion3": 3.4, "camion4": 4.0, "camion5": 4.6, "camion6": 5.2,
}


# Factor de tiempo de viaje relativo al automóvil (base auto = 1.0). Vehículos
# pesados circulan más lento (límites de velocidad menores y menor aceleración);
# la moto es ligeramente más ágil en tráfico.
TIME_FACTORS = {
    "moto": 0.97, "auto": 1.0, "autobus": 1.12,
    "camion2": 1.12, "camion3": 1.18, "camion4": 1.22, "camion5": 1.28, "camion6": 1.33,
}


def time_factor_for(vehicle_class: str) -> float:
    vc = vehicle_class if vehicle_class in VEHICLE_CLASS_KEYS else DEFAULT_VEHICLE_CLASS
    return TIME_FACTORS.get(vc, 1.0)


def fuel_factor_for(vehicle_class: str) -> float:
    vc = vehicle_class if vehicle_class in VEHICLE_CLASS_KEYS else DEFAULT_VEHICLE_CLASS
    return FUEL_FACTORS.get(vc, 1.0)


def _p(moto, auto, autobus, c2, c3, c4, c5, c6):
    return {"moto": moto, "auto": auto, "autobus": autobus,
            "camion2": c2, "camion3": c3, "camion4": c4, "camion5": c5, "camion6": c6}


# name, autopista, lat, lng, prices
CASETAS: List[Dict] = [
    # ===== México–Querétaro (CAPUFE) =====
    {"name": "Tepotzotlán", "autopista": "México–Querétaro", "lat": 19.7167, "lng": -99.2236, "prices": _p(56, 113, 269, 257, 257, 517, 517, 743)},
    {"name": "Jorobas", "autopista": "México–Querétaro (Jorobas–Tepeji)", "lat": 19.8600, "lng": -99.3300, "prices": _p(37, 74, 141, 140, 140, 278, 278, 399)},
    {"name": "Palmillas", "autopista": "México–Querétaro", "lat": 20.0986, "lng": -99.7400, "prices": _p(56, 113, 251, 240, 240, 482, 482, 703)},
    {"name": "Polotitlán", "autopista": "México–Querétaro", "lat": 20.2236, "lng": -99.8090, "prices": _p(51, 103, 216, 210, 210, 415, 415, 583)},

    # ===== México–Cuernavaca (CAPUFE) =====
    {"name": "Tlalpan", "autopista": "México–Cuernavaca", "lat": 19.2333, "lng": -99.1670, "prices": _p(78, 156, 301, 299, 299, 512, 512, 748)},
    {"name": "Tres Marías", "autopista": "México–Cuernavaca", "lat": 19.0480, "lng": -99.2370, "prices": _p(28, 56, 132, 128, 128, 252, 252, 365)},

    # ===== México–Puebla (CAPUFE) =====
    {"name": "Chalco", "autopista": "México–Puebla", "lat": 19.2750, "lng": -98.8950, "prices": _p(13, 26, 52, 50, 50, 81, 81, 127)},
    {"name": "Ixtapaluca", "autopista": "México–Puebla", "lat": 19.3100, "lng": -98.8800, "prices": _p(13, 26, 52, 50, 50, 81, 81, 127)},
    {"name": "San Marcos", "autopista": "México–Puebla", "lat": 19.2960, "lng": -98.4690, "prices": _p(86, 173, 350, 335, 335, 688, 688, 943)},
    {"name": "San Martín Texmelucan", "autopista": "México–Puebla", "lat": 19.2700, "lng": -98.4400, "prices": _p(26, 53, 137, 129, 129, 261, 261, 366)},
    {"name": "Amozoc", "autopista": "Puebla–Acatzingo", "lat": 19.0480, "lng": -98.0400, "prices": _p(47, 94, 196, 187, 187, 360, 360, 480)},

    # ===== Puebla–Orizaba–Córdoba–Veracruz (CAPUFE) =====
    {"name": "Esperanza (Cumbres de Maltrata)", "autopista": "Acatzingo–Cd. Mendoza", "lat": 18.8550, "lng": -97.3700, "prices": _p(89, 178, 409, 386, 386, 745, 745, 1085)},
    {"name": "Fortín", "autopista": "Cd. Mendoza–Córdoba", "lat": 18.8900, "lng": -96.9900, "prices": _p(21, 43, 112, 93, 93, 180, 180, 241)},
    {"name": "Cuitláhuac", "autopista": "Córdoba–La Tinaja", "lat": 18.8100, "lng": -96.7200, "prices": _p(73, 146, 208, 195, 195, 278, 278, 292)},
    {"name": "Paso del Toro", "autopista": "La Tinaja–Veracruz", "lat": 19.0600, "lng": -96.1600, "prices": _p(68, 136, 226, 223, 223, 288, 288, 336)},

    # ===== Querétaro–Irapuato (CAPUFE) =====
    {"name": "Querétaro (Palmillas Qro)", "autopista": "Querétaro–Celaya", "lat": 20.5050, "lng": -100.6300, "prices": _p(53, 107, 225, 216, 216, 425, 425, 596)},
    {"name": "Apaseo", "autopista": "Querétaro–Celaya", "lat": 20.4700, "lng": -100.6700, "prices": _p(24, 49, 99, 99, 99, 193, 193, 269)},
    {"name": "Salamanca", "autopista": "Celaya–Salamanca", "lat": 20.5400, "lng": -101.0500, "prices": _p(36, 73, 173, 170, 170, 330, 330, 445)},
    {"name": "Cerro Gordo", "autopista": "Celaya–Irapuato", "lat": 20.5300, "lng": -100.9000, "prices": _p(30, 61, 132, 134, 134, 232, 232, 342)},

    # ===== Chamapa–Lechería (CAPUFE) =====
    {"name": "Chamapa", "autopista": "Chamapa–Lechería", "lat": 19.5050, "lng": -99.2700, "prices": _p(30, 61, 127, 119, 119, 183, 183, 228)},
    {"name": "Cipreses", "autopista": "Chamapa–Lechería", "lat": 19.5300, "lng": -99.2400, "prices": _p(31, 62, 114, 113, 113, 166, 166, 218)},

    # ===== Libramiento NE Querétaro =====
    {"name": "Chichimequillas", "autopista": "Libramiento Nororiente de Querétaro", "lat": 20.7200, "lng": -100.3300, "prices": _p(32, 65, 118, 112, 112, 121, 121, 166)},

    # ===== Autopista del Sol: México–Cuernavaca–Acapulco (CAPUFE) =====
    {"name": "Alpuyeca", "autopista": "Cuernavaca–Alpuyeca", "lat": 18.7470, "lng": -99.2750, "prices": _p(34, 68, 124, 122, 122, 153, 153, 172)},
    {"name": "Paso Morelos", "autopista": "Puente de Ixtla–Chilpancingo", "lat": 18.1300, "lng": -99.4300, "prices": _p(104, 209, 453, 449, 449, 591, 591, 654)},
    {"name": "Palo Blanco", "autopista": "Chilpancingo–Tierra Colorada", "lat": 17.4500, "lng": -99.4800, "prices": _p(95, 190, 262, 262, 262, 345, 345, 386)},
    {"name": "La Venta", "autopista": "Tierra Colorada–Acapulco", "lat": 16.9500, "lng": -99.7800, "prices": _p(85, 171, 248, 245, 245, 335, 335, 375)},
    {"name": "Iguala", "autopista": "Puente de Ixtla–Iguala", "lat": 18.3700, "lng": -99.5200, "prices": _p(56, 112, 238, 237, 237, 435, 435, 596)},

    # ===== La Pera–Cuautla (CAPUFE) =====
    {"name": "La Pera", "autopista": "La Pera–Cuautla", "lat": 18.9870, "lng": -99.0490, "prices": _p(43, 86, 159, 156, 156, 254, 254, 374)},
    {"name": "Tepoztlán", "autopista": "La Pera–Cuautla", "lat": 18.9750, "lng": -99.0900, "prices": _p(16, 33, 60, 58, 58, 98, 98, 140)},
    {"name": "Oacalco", "autopista": "La Pera–Cuautla", "lat": 18.8900, "lng": -99.0500, "prices": _p(26, 53, 100, 98, 98, 159, 159, 234)},

    # ===== Tehuacán–Oaxaca (CAPUFE) =====
    {"name": "Tehuacán", "autopista": "Cuacnopalan–Oaxaca", "lat": 18.5000, "lng": -97.4500, "prices": _p(29, 58, 138, 136, 136, 170, 170, 266)},
    {"name": "Suchixtlahuaca", "autopista": "Cuacnopalan–Oaxaca", "lat": 17.6500, "lng": -97.3500, "prices": _p(49, 99, 218, 217, 217, 264, 264, 368)},
    {"name": "Huitzo", "autopista": "Nochixtlán–Oaxaca", "lat": 17.2700, "lng": -96.8800, "prices": _p(57, 114, 275, 274, 274, 319, 319, 497)},

    # ===== Barranca Larga–Ventanilla (Oaxaca costa) =====
    {"name": "Barranca Larga", "autopista": "Oaxaca–Puerto Escondido", "lat": 16.9000, "lng": -96.7500, "prices": _p(122, 245, 490, 490, 490, 734, 734, 1102)},

    # ===== Estación Don–Nogales (Sonora, CAPUFE) =====
    {"name": "Estación Don", "autopista": "Estación Don–Navojoa", "lat": 27.0200, "lng": -109.5300, "prices": _p(57, 114, 194, 191, 191, 287, 287, 330)},
    {"name": "Esperanza (Sonora)", "autopista": "Cd. Obregón–Guaymas", "lat": 27.7600, "lng": -110.4500, "prices": _p(57, 114, 194, 190, 190, 287, 287, 330)},

    # ===== Tijuana–Ensenada (CAPUFE) =====
    {"name": "Playas de Tijuana", "autopista": "Tijuana–Rosarito", "lat": 32.5100, "lng": -117.1100, "prices": _p(25, 50, 109, 109, 109, 131, 131, 152)},
    {"name": "Ensenada (El Mirador)", "autopista": "La Misión–Ensenada", "lat": 31.8700, "lng": -116.6600, "prices": _p(26, 53, 114, 110, 110, 136, 136, 160)},

    # ===== El Zacatal (Campeche) =====
    {"name": "El Zacatal", "autopista": "Zacatal–Cd. del Carmen", "lat": 18.6400, "lng": -91.8200, "prices": _p(57, 114, 252, 251, 251, 407, 407, 506)},

    # ===== Arco Norte (concesión — tarifas 2026 aprox.) =====
    {"name": "Ajoloapan", "autopista": "Arco Norte", "lat": 19.8000, "lng": -99.0000, "prices": _p(67, 135, 264, 264, 351, 446, 608, 703)},
    {"name": "Tula (Arco Norte)", "autopista": "Arco Norte", "lat": 20.0500, "lng": -99.3500, "prices": _p(69, 138, 270, 270, 359, 456, 622, 719)},
    {"name": "Sanctorum", "autopista": "Arco Norte", "lat": 19.4900, "lng": -98.4300, "prices": _p(69, 138, 270, 270, 359, 456, 622, 719)},
    {"name": "Texmelucan (Arco Norte)", "autopista": "Arco Norte", "lat": 19.3500, "lng": -98.4200, "prices": _p(35, 70, 137, 137, 182, 231, 315, 364)},
    {"name": "Calpulalpan", "autopista": "Arco Norte", "lat": 19.5800, "lng": -98.5700, "prices": _p(45, 90, 176, 176, 234, 297, 405, 468)},
]


def haversine_m(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    R = 6371000.0
    lat1, lng1 = math.radians(a[0]), math.radians(a[1])
    lat2, lng2 = math.radians(b[0]), math.radians(b[1])
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def caseta_price(caseta: Dict, vehicle_class: str) -> float:
    vc = vehicle_class if vehicle_class in VEHICLE_CLASS_KEYS else DEFAULT_VEHICLE_CLASS
    prices = caseta.get("prices", {})
    val = prices.get(vc)
    if val is None:
        val = round(prices.get("auto", FALLBACK_AUTO_MXN) * FALLBACK_FACTORS.get(vc, 1.0))
    return float(val)


def fallback_price(vehicle_class: str) -> float:
    vc = vehicle_class if vehicle_class in VEHICLE_CLASS_KEYS else DEFAULT_VEHICLE_CLASS
    return round(FALLBACK_AUTO_MXN * FALLBACK_FACTORS.get(vc, 1.0), 2)


def nearest_caseta(lat: float, lng: float, max_m: float = 8000.0) -> Optional[Dict]:
    """Return the dataset caseta closest to (lat,lng) within max_m, else None."""
    best, best_d = None, max_m
    for c in CASETAS:
        d = haversine_m((lat, lng), (c["lat"], c["lng"]))
        if d <= best_d:
            best, best_d = c, d
    return best
