"""
Map PyJHora (jhora) outputs into the app's normalized chart package.

Depends on PyJHora, pyswisseph, geopy, and geocoder (jhora imports jhora.utils).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from zoneinfo import ZoneInfo

from geopy.geocoders import Nominatim

from jhora import const as jhora_const
from jhora import utils as jhora_utils
from jhora.horoscope.chart import charts, house as jhora_house
from jhora.horoscope.dhasa.graha import vimsottari
from jhora.panchanga import drik

from astrology_app.models import BirthInput

SIGN_NAMES = [
    "aries",
    "taurus",
    "gemini",
    "cancer",
    "leo",
    "virgo",
    "libra",
    "scorpio",
    "sagittarius",
    "capricorn",
    "aquarius",
    "pisces",
]

NAKSHATRA_NAMES = [
    "ashwini",
    "bharani",
    "krittika",
    "rohini",
    "mrigashira",
    "ardra",
    "punarvasu",
    "pushya",
    "ashlesha",
    "magha",
    "purva_phalguni",
    "uttara_phalguni",
    "hasta",
    "chitra",
    "swati",
    "vishakha",
    "anuradha",
    "jyeshtha",
    "mula",
    "purva_ashadha",
    "uttara_ashadha",
    "shravana",
    "dhanishta",
    "shatabhisha",
    "purva_bhadrapada",
    "uttara_bhadrapada",
    "revati",
]

PLANET_NAMES = {
    jhora_const.SUN_ID: "sun",
    jhora_const.MOON_ID: "moon",
    jhora_const.MARS_ID: "mars",
    jhora_const.MERCURY_ID: "mercury",
    jhora_const.JUPITER_ID: "jupiter",
    jhora_const.VENUS_ID: "venus",
    jhora_const.SATURN_ID: "saturn",
    jhora_const.RAHU_ID: "rahu",
    jhora_const.KETU_ID: "ketu",
}

VARGA_FACTORS = {
    "d1": 1,
    "d2": 2,
    "d3": 3,
    "d4": 4,
    "d7": 7,
    "d9": 9,
    "d10": 10,
    "d12": 12,
    "d16": 16,
    "d20": 20,
    "d24": 24,
    "d27": 27,
    "d30": 30,
    "d40": 40,
    "d45": 45,
    "d60": 60,
}


def generate_pyjhora_chart_package(birth_input: BirthInput) -> dict:
    jhora_const._DEFAULT_AYANAMSA_MODE = "LAHIRI"

    lat, lon = _resolved_coordinates(birth_input)
    tz_hours = _timezone_offset_hours_at_birth(
        birth_input.timezone,
        birth_input.date_of_birth,
        birth_input.time_of_birth,
    )
    place = drik.Place(birth_input.birth_place, lat, lon, tz_hours)

    y, m, d = _parse_ymd(birth_input.date_of_birth)
    hh, mm = _parse_hm(birth_input.time_of_birth)
    jd = _julian_day_number((y, m, d), (hh, mm, 0))

    raw_charts = {
        key: charts.divisional_chart(
            jd,
            place,
            divisional_chart_factor=factor,
            chart_method=1,
        )
        for key, factor in VARGA_FACTORS.items()
    }

    normalized_charts = {
        key: _serialize_chart(
            positions=positions,
            lagna_sign=int(positions[0][1][0]),
            include_nakshatra_pada=(key == "d1"),
        )
        for key, positions in raw_charts.items()
    }

    d1 = raw_charts["d1"]
    lagna_sign_d1 = int(d1[0][1][0])
    derived = _build_derived_features(d1, lagna_sign_d1)
    nakshatras = _nakshatras_from_d1(d1)

    jd_now = _now_jd_same_convention(birth_input.timezone)
    dashas = _vimshottari_summary(jd, jd_now, place)

    return {
        "source": "pyjhora-adapter",
        "input": asdict(birth_input),
        "metadata": {
            "ayanamsha_mode": "LAHIRI",
            "dasha_system": "vimshottari",
            "charts_included": list(VARGA_FACTORS.keys()),
            "status": "computed",
            "resolved_location": {
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "timezone_offset_hours": tz_hours,
            },
        },
        "charts": normalized_charts,
        "derived": derived,
        "dashas": dashas,
        "nakshatras": nakshatras,
        "notes": [
            "Computed with PyJHora divisional_chart and Vimshottari routines.",
            "Birth time is interpreted as local civil time in the resolved IANA timezone.",
            "Derived D1 features include house lords, occupancies, dignities, conjunctions, and graha drishti.",
        ],
    }


def _build_derived_features(d1_positions: list, lagna_sign: int) -> dict:
    house_to_planet = jhora_utils.get_house_planet_list_from_planet_positions(d1_positions)
    combust_planets = set(
        charts.planets_in_combustion(d1_positions, use_absolute_longitude=True)
    )
    return {
        "houses": _houses_from_d1(d1_positions, lagna_sign, house_to_planet),
        "house_lords": _house_lords_from_d1(d1_positions, lagna_sign),
        "dignities": _dignities_from_d1(d1_positions, combust_planets),
        "aspects": _aspects_from_d1(house_to_planet),
        "conjunctions": _conjunctions_from_d1(d1_positions, lagna_sign),
    }


def _houses_from_d1(d1_positions: list, lagna_sign: int, house_to_planet: list[str]) -> dict:
    houses: dict[str, dict] = {}
    for house_num in range(1, 13):
        sign_idx = (lagna_sign + house_num - 1) % 12
        occupants = [
            _planet_name(int(pid))
            for pid, (planet_sign, _lon) in d1_positions[1:]
            if _is_supported_planet(int(pid))
            if ((int(planet_sign) - lagna_sign) % 12 + 1) == house_num
        ]
        aspected_by = [
            _planet_name(int(pid))
            for pid in jhora_house.planets_aspecting_the_raasi(house_to_planet, sign_idx)
            if _is_supported_planet(int(pid))
        ]
        houses[str(house_num)] = {
            "sign": SIGN_NAMES[sign_idx],
            "occupants": occupants,
            "aspected_by": sorted(set(aspected_by)),
        }
    return houses


def _house_lords_from_d1(d1_positions: list, lagna_sign: int) -> dict:
    house_lords: dict[str, dict] = {}
    planet_lookup = {
        _planet_name(int(pid)): {
            "sign": SIGN_NAMES[int(sign)],
            "house": (int(sign) - lagna_sign) % 12 + 1,
            "longitude_in_sign_degrees": round(float(lon), 4),
        }
        for pid, (sign, lon) in d1_positions[1:]
        if _is_supported_planet(int(pid))
    }
    for house_num in range(1, 13):
        sign_idx = (lagna_sign + house_num - 1) % 12
        lord_id = int(jhora_const.house_owners[sign_idx])
        lord_name = _planet_name(lord_id)
        house_lords[str(house_num)] = {
            "sign": SIGN_NAMES[sign_idx],
            "lord": lord_name,
            "lord_placement": planet_lookup[lord_name],
        }
    return house_lords


def _dignities_from_d1(d1_positions: list, combust_planets: set[int]) -> dict:
    dignities: dict[str, dict] = {}
    for pid, (sign, lon) in d1_positions[1:]:
        planet_id = int(pid)
        if not _is_supported_planet(planet_id):
            continue
        sign_idx = int(sign)
        strength = int(jhora_const.house_strengths_of_planets[planet_id][sign_idx])
        dignities[_planet_name(planet_id)] = {
            "sign": SIGN_NAMES[sign_idx],
            "strength_label": jhora_const.house_strength_types[strength],
            "dignity": _dignity_label(planet_id, sign_idx, float(lon), d1_positions),
            "is_combust": planet_id in combust_planets,
        }
    return dignities


def _dignity_label(
    planet_id: int,
    sign_idx: int,
    longitude_in_sign: float,
    d1_positions: list,
) -> str:
    if jhora_utils.is_planet_in_exalation(
        planet_id,
        sign_idx,
        planet_positions=d1_positions,
    ):
        return "exalted"
    if jhora_utils.is_planet_in_debilitation(
        planet_id,
        sign_idx,
        planet_positions=d1_positions,
    ):
        return "debilitated"
    if jhora_utils.is_planet_in_moolatrikona(
        planet_id,
        p_pos_tuple=(sign_idx, longitude_in_sign),
        enforce_trikona_degrees=True,
    ):
        return "moolatrikona"

    strength = int(jhora_const.house_strengths_of_planets[planet_id][sign_idx])
    if strength == jhora_const._OWNER_RULER:
        return "own_sign"
    if strength >= jhora_const._FRIEND:
        return "favorable_sign"
    if strength == jhora_const._NEUTRAL_SAMAM:
        return "neutral_sign"
    return "challenging_sign"


def _aspects_from_d1(house_to_planet: list[str]) -> dict:
    graha_drishti: dict[str, dict] = {}
    for planet_id, planet_name in PLANET_NAMES.items():
        graha_drishti[planet_name] = {
            "houses": [
                int(house_num) + 1
                for house_num in jhora_house.aspected_houses_of_the_planet(
                    house_to_planet, planet_id
                )
            ],
            "signs": [
                SIGN_NAMES[int(sign_idx)]
                for sign_idx in jhora_house.aspected_rasis_of_the_planet(
                    house_to_planet, planet_id
                )
            ],
            "planets": [
                PLANET_NAMES[int(pid)]
                for pid in jhora_house.aspected_planets_of_the_planet(
                    house_to_planet, planet_id
                )
                if int(pid) in PLANET_NAMES
            ],
        }
    return {"graha_drishti": graha_drishti}


def _conjunctions_from_d1(d1_positions: list, lagna_sign: int) -> list[dict]:
    conjunctions: list[dict] = []
    for house_num in range(1, 13):
        occupants = [
            _planet_name(int(pid))
            for pid, (planet_sign, _lon) in d1_positions[1:]
            if _is_supported_planet(int(pid))
            if ((int(planet_sign) - lagna_sign) % 12 + 1) == house_num
        ]
        if len(occupants) > 1:
            conjunctions.append({"house": house_num, "planets": occupants})
    return conjunctions


def _resolved_coordinates(birth_input: BirthInput) -> tuple[float, float]:
    if birth_input.latitude or birth_input.longitude:
        return birth_input.latitude, birth_input.longitude
    return _geocode(birth_input.birth_place)


def _geocode(place: str) -> tuple[float, float]:
    geolocator = Nominatim(user_agent="astrology-ai/0.1")
    location = geolocator.geocode(place, timeout=15)
    if location is None:
        raise ValueError(
            "Could not geocode the birth place. Try 'City, State, Country' or add detail."
        )
    return float(location.latitude), float(location.longitude)


def _timezone_offset_hours_at_birth(
    tz_name: str, date_str: str, time_str: str
) -> float:
    y, m, d = _parse_ymd(date_str)
    hh, mm = _parse_hm(time_str)
    dt = datetime(y, m, d, hh, mm, tzinfo=ZoneInfo(tz_name))
    off = dt.utcoffset()
    if off is None:
        raise ValueError(f"Invalid timezone for offset calculation: {tz_name}")
    return off.total_seconds() / 3600.0


def _parse_ymd(date_str: str) -> tuple[int, int, int]:
    parts = date_str.strip().split("-")
    if len(parts) != 3:
        raise ValueError("Date must be YYYY-MM-DD.")
    y, m, d = (int(parts[0]), int(parts[1]), int(parts[2]))
    return y, m, d


def _parse_hm(time_str: str) -> tuple[int, int]:
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValueError("Time must be HH:MM.")
    return int(parts[0]), int(parts[1])


def _julian_day_number(dob: tuple[int, int, int], tob: tuple[int, int, int]) -> float:
    return jhora_utils.julian_day_number(dob, tob)


def _now_jd_same_convention(tz_name: str) -> float:
    now = datetime.now(ZoneInfo(tz_name))
    return _julian_day_number(
        (now.year, now.month, now.day), (now.hour, now.minute, now.second)
    )


def _serialize_chart(
    positions: list, lagna_sign: int, *, include_nakshatra_pada: bool
) -> dict:
    asc = positions[0]
    asc_sign, asc_lon = asc[1]
    asc_sign = int(asc_sign)
    out: dict = {
        "ascendant": {
            "sign": SIGN_NAMES[asc_sign],
            "longitude_in_sign_degrees": round(float(asc_lon), 4),
            "house": 1,
        },
        "planets": {},
    }
    for entry in positions[1:]:
        pid = int(entry[0])
        if not _is_supported_planet(pid):
            continue
        sgn, lon = entry[1]
        sgn = int(sgn)
        pname = _planet_name(pid)
        house_num = (sgn - lagna_sign) % 12 + 1
        planet_data: dict = {
            "sign": SIGN_NAMES[sgn],
            "longitude_in_sign_degrees": round(float(lon), 4),
            "house": house_num,
        }
        if include_nakshatra_pada:
            full_long = (sgn * 30.0 + float(lon)) % 360.0
            nk, pada, _rem = drik.nakshatra_pada(full_long)
            planet_data["nakshatra"] = NAKSHATRA_NAMES[int(nk) - 1]
            planet_data["pada"] = int(pada)
        out["planets"][pname] = planet_data
    return out


def _nakshatras_from_d1(d1: list) -> dict:
    moon_entry = next(p for p in d1[1:] if p[0] == jhora_const.MOON_ID)
    sgn, lon = moon_entry[1]
    full_long = (int(sgn) * 30.0 + float(lon)) % 360.0
    nk, pada, _rem = drik.nakshatra_pada(full_long)
    by_planet: dict = {}
    for entry in d1[1:]:
        pid = int(entry[0])
        if not _is_supported_planet(pid):
            continue
        sgn, lon = entry[1]
        full_long = (int(sgn) * 30.0 + float(lon)) % 360.0
        nkk, pd, _ = drik.nakshatra_pada(full_long)
        by_planet[_planet_name(pid)] = {
            "name": NAKSHATRA_NAMES[int(nkk) - 1],
            "pada": int(pd),
        }
    return {
        "moon": {"name": NAKSHATRA_NAMES[int(nk) - 1], "pada": int(pada)},
        "by_planet": by_planet,
    }


def _planet_name_from_dasha_lord(lord: int | tuple) -> str:
    current = lord
    while isinstance(current, tuple) and current:
        current = current[-1]
    if isinstance(current, int):
        return _planet_name(current)
    return str(current)


def _is_supported_planet(planet_id: int) -> bool:
    return planet_id in PLANET_NAMES


def _planet_name(planet_id: int) -> str:
    return PLANET_NAMES.get(planet_id, f"planet_{planet_id}")


def _vimshottari_summary(jd_birth: float, jd_now: float, place) -> dict:
    running = vimsottari.get_running_dhasa_for_given_date(
        jd_now,
        jd_birth,
        place,
        dhasa_level_index=jhora_const.MAHA_DHASA_DEPTH.PRATYANTARA,
    )
    if len(running) < 2:
        raise RuntimeError("Unexpected Vimshottari depth result from PyJHora.")

    current_levels = {}
    level_names = [
        "current_mahadasha",
        "current_antardasha",
        "current_pratyantardasha",
    ]
    for level_name, row in zip(level_names, running):
        current_levels[level_name] = _planet_name_from_dasha_lord(row[0])

    md = vimsottari.vimsottari_mahadasa(jd_birth, place)
    sequence: list[dict] = []
    for lord_id, start_jd in md.items():
        gy, gm, gd, gfh = jhora_utils.jd_to_gregorian(start_jd)
        sequence.append(
            {
                "lord": _planet_name_from_dasha_lord(int(lord_id)),
                "start": {
                    "year": int(gy),
                    "month": int(gm),
                    "day": int(gd),
                    "fractional_hour": float(gfh),
                },
            }
        )

    return {
        **current_levels,
        "as_of": {
            "julian_day": jd_now,
            "timezone": "same as birth input timezone for 'now'",
        },
        "sequence": sequence,
    }
