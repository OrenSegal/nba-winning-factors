"""Arena locations and franchise identity for the travel, altitude and Elo factors.

Keyed by the abbreviation the game log uses for the home team, so a relocated
franchise (SEA, NOK, VAN, ...) maps to the city it actually played in that season.
"""

import numpy as np

# abbreviation -> (latitude, longitude, altitude in feet, standard-time UTC offset)
ARENAS = {
    "ATL": (33.757, -84.396, 1050, -5), "BKN": (40.683, -73.975, 30, -5), "BOS": (42.366, -71.062, 20, -5),
    "CHA": (35.225, -80.839, 750, -5), "CHH": (35.225, -80.839, 750, -5), "CHI": (41.881, -87.674, 600, -6),
    "CLE": (41.497, -81.688, 650, -5), "DAL": (32.790, -96.810, 430, -6), "DEN": (39.749, -105.008, 5280, -7),
    "DET": (42.341, -83.055, 600, -5), "GSW": (37.768, -122.388, 10, -8), "HOU": (29.751, -95.362, 40, -6),
    "IND": (39.764, -86.156, 715, -5), "LAC": (34.043, -118.267, 270, -8), "LAL": (34.043, -118.267, 270, -8),
    "MEM": (35.138, -90.051, 260, -6), "MIA": (25.781, -80.187, 10, -5), "MIL": (43.045, -87.917, 600, -6),
    "MIN": (44.979, -93.276, 830, -6), "NJN": (40.733, -74.171, 10, -5), "NOH": (29.949, -90.082, 5, -6),
    "NOK": (35.463, -97.515, 1200, -6), "NOP": (29.949, -90.082, 5, -6), "NYK": (40.751, -73.994, 30, -5),
    "OKC": (35.463, -97.515, 1200, -6), "ORL": (28.539, -81.384, 100, -5), "PHI": (39.901, -75.172, 20, -5),
    "PHX": (33.446, -112.071, 1100, -7), "POR": (45.532, -122.667, 50, -8), "SAC": (38.580, -121.500, 30, -8),
    "SAS": (29.427, -98.438, 650, -6), "SEA": (47.622, -122.354, 50, -8), "TOR": (43.643, -79.379, 250, -5),
    "UTA": (40.768, -111.901, 4226, -7), "VAN": (49.278, -123.109, 10, -8), "WAS": (38.898, -77.021, 25, -5),
}

# Same franchise under an earlier name (the Charlotte Hornets became the New Orleans franchise in 2002).
FRANCHISE = {"SEA": "OKC", "NJN": "BKN", "NOH": "NOP", "NOK": "NOP", "CHH": "NOP", "VAN": "MEM"}


def franchise(abbr: str) -> str:
    return FRANCHISE.get(abbr, abbr)


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))
