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
from jhora.horoscope.dhasa import sudharsana_chakra
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
    "d6": 6,
    "d7": 7,
    "d8": 8,
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
    dashas = _vimshottari_summary(jd, jd_now, place, d1)
    transits = _current_transit_summary(jd_now, place, birth_input.timezone)
    relationship_transits = _yearly_relationship_transits(
        birth_input=birth_input,
        place=place,
        lagna_sign_d1=lagna_sign_d1,
        d1_positions=d1,
    )
    sudarshana = _sudarshana_chakra_summary(jd, place, birth_input)

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
        "sudarshana_chakra": sudarshana,
        "transits": {
            **transits,
            "yearly_relationship": relationship_transits,
        },
        "nakshatras": nakshatras,
        "notes": [
            "Computed with PyJHora divisional_chart and Vimshottari routines.",
            "Birth time is interpreted as local civil time in the resolved IANA timezone.",
            "Derived D1 features include house lords, occupancies, dignities, conjunctions, and graha drishti.",
            "Current transit snapshot is included as present-time gochara support.",
            "Sudarshana Chakra is included as a normalized current-cycle composite reference.",
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


def _jd_from_local_datetime(
    *,
    tz_name: str,
    year: int,
    month: int,
    day: int,
    hour: int = 12,
    minute: int = 0,
    second: int = 0,
) -> float:
    local_dt = datetime(year, month, day, hour, minute, second, tzinfo=ZoneInfo(tz_name))
    return _julian_day_number(
        (local_dt.year, local_dt.month, local_dt.day),
        (local_dt.hour, local_dt.minute, local_dt.second),
    )


def _completed_years_at_now(birth_input: BirthInput) -> int:
    y, m, d = _parse_ymd(birth_input.date_of_birth)
    hh, mm = _parse_hm(birth_input.time_of_birth)
    now = datetime.now(ZoneInfo(birth_input.timezone))
    years = now.year - y
    if (now.month, now.day, now.hour, now.minute) < (m, d, hh, mm):
        years -= 1
    return max(0, years)


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


def _serialize_sudarshana_chart(chart_rows: list[tuple[int, str]]) -> list[dict]:
    serialized: list[dict] = []
    for house_num, (sign_idx, occupants) in enumerate(chart_rows, start=1):
        planet_ids = [entry for entry in str(occupants).split("/") if entry.strip()]
        normalized_occupants: list[str] = []
        for planet_id in planet_ids:
            if planet_id == "L":
                normalized_occupants.append("lagna")
            elif planet_id.lstrip("-").isdigit() and int(planet_id) in PLANET_NAMES:
                normalized_occupants.append(_planet_name(int(planet_id)))
            else:
                normalized_occupants.append(str(planet_id))
        serialized.append(
            {
                "house": house_num,
                "sign": SIGN_NAMES[int(sign_idx)],
                "occupants": normalized_occupants,
            }
        )
    return serialized


def _current_transit_summary(jd_now: float, place, tz_name: str) -> dict:
    transit_positions = charts.divisional_chart(jd_now, place, divisional_chart_factor=1)
    retrograde_planets = [
        _planet_name(int(pid))
        for pid in drik.planets_in_retrograde(jd_now, place)
        if int(pid) in PLANET_NAMES
    ]
    y, m, d, fh = jhora_utils.jd_to_gregorian(jd_now)
    return {
        "current": {
            "as_of": {
                "year": int(y),
                "month": int(m),
                "day": int(d),
                "fractional_hour": float(fh),
                "timezone": tz_name,
            },
            "chart": _serialize_chart(
                positions=transit_positions,
                lagna_sign=int(transit_positions[0][1][0]),
                include_nakshatra_pada=False,
            ),
            "retrograde_planets": retrograde_planets,
        }
    }


def _sudarshana_chakra_summary(jd_birth: float, place, birth_input: BirthInput) -> dict:
    completed_years = _completed_years_at_now(birth_input)
    running_year_number = max(1, completed_years + 1)
    dob = _parse_ymd(birth_input.date_of_birth)
    lagna_chart, moon_chart, sun_chart, retrograde = sudharsana_chakra.sudharshana_chakra_chart(
        jd_birth,
        place,
        dob,
        years_from_dob=running_year_number,
        divisional_chart_factor=1,
    )
    return {
        "current_cycle": {
            "reference": {
                "completed_years": completed_years,
                "running_year_number": running_year_number,
            },
            "lagna_chart": _serialize_sudarshana_chart(lagna_chart),
            "moon_chart": _serialize_sudarshana_chart(moon_chart),
            "sun_chart": _serialize_sudarshana_chart(sun_chart),
            "retrograde_planets": [
                _planet_name(int(pid)) for pid in retrograde if int(pid) in PLANET_NAMES
            ],
        }
    }


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


def _sign_name_from_index(sign_idx: int) -> str:
    return SIGN_NAMES[int(sign_idx) % 12]


def _gregorian_tuple_to_dict(gregorian: tuple[float, float, float, float]) -> dict:
    gy, gm, gd, gfh = gregorian
    return {
        "year": int(gy),
        "month": int(gm),
        "day": int(gd),
        "fractional_hour": float(gfh),
    }


def _dasha_row_to_dict(lords_tuple, start_tuple, duration_years: float) -> dict:
    start_dict = _gregorian_tuple_to_dict(start_tuple)
    start_jd = _julian_day_number(
        (start_dict["year"], start_dict["month"], start_dict["day"]),
        (start_dict["fractional_hour"], 0, 0),
    )
    end_jd = start_jd + float(duration_years) * vimsottari.year_duration
    end_tuple = jhora_utils.jd_to_gregorian(end_jd)
    row = {
        "start": start_dict,
        "end": _gregorian_tuple_to_dict(end_tuple),
        "duration_years": float(duration_years),
    }
    tuple_lords = tuple(lords_tuple) if isinstance(lords_tuple, tuple) else tuple(lords_tuple)
    if len(tuple_lords) >= 1:
        row["mahadasha_lord"] = _planet_name_from_dasha_lord(tuple_lords[0])
    if len(tuple_lords) >= 2:
        row["antardasha_lord"] = _planet_name_from_dasha_lord(tuple_lords[1])
    if len(tuple_lords) >= 3:
        row["pratyantardasha_lord"] = _planet_name_from_dasha_lord(tuple_lords[2])
    return row


def _birth_vimshottari_balance(jd_birth: float, place, d1_positions: list) -> dict:
    moon_entry = next(entry for entry in d1_positions[1:] if int(entry[0]) == jhora_const.MOON_ID)
    sign_idx, lon_in_sign = moon_entry[1]
    full_long = (int(sign_idx) * 30.0 + float(lon_in_sign)) % 360.0
    one_star = vimsottari.one_star
    nak_index = int(full_long / one_star)
    nak_progress = (full_long - nak_index * one_star) / one_star
    remaining_fraction = 1.0 - nak_progress
    lord_id = vimsottari.vimsottari_adhipati(nak_index)
    lord_name = _planet_name_from_dasha_lord(lord_id)
    md_years = float(vimsottari.vimsottari_dict[lord_id])
    years_remaining = md_years * remaining_fraction
    _start_lord, md_start_jd = vimsottari.vimsottari_dasha_start_date(jd_birth, place)
    md_end_jd = md_start_jd + md_years * vimsottari.year_duration
    return {
        "moon_nakshatra": NAKSHATRA_NAMES[nak_index],
        "moon_pada": int(drik.nakshatra_pada(full_long)[1]),
        "mahadasha_lord_at_birth": lord_name,
        "elapsed_fraction": float(nak_progress),
        "remaining_fraction": float(remaining_fraction),
        "remaining_percentage": float(remaining_fraction * 100.0),
        "years_remaining_in_birth_mahadasha": years_remaining,
        "birth_mahadasha_start": _gregorian_tuple_to_dict(jhora_utils.jd_to_gregorian(md_start_jd)),
        "birth_mahadasha_end": _gregorian_tuple_to_dict(jhora_utils.jd_to_gregorian(md_end_jd)),
    }


def _relationship_target_flags(
    *,
    transit_positions: list,
    lagna_sign_d1: int,
    natal_venus_sign: int,
) -> dict[str, dict[str, bool | int | str]]:
    house_to_planet = jhora_utils.get_house_planet_list_from_planet_positions(transit_positions)
    natal_target_signs = {
        "1st_house_sign": lagna_sign_d1,
        "5th_house_sign": (lagna_sign_d1 + 4) % 12,
        "7th_house_sign": (lagna_sign_d1 + 6) % 12,
        "venus_sign": natal_venus_sign,
    }
    flags: dict[str, dict[str, bool | int | str]] = {}
    for planet_id in (jhora_const.SATURN_ID, jhora_const.JUPITER_ID, jhora_const.RAHU_ID, jhora_const.KETU_ID):
        transit_sign = int(transit_positions[planet_id + 1][1][0])
        aspected_signs = {
            int(sign_idx)
            for sign_idx in jhora_house.aspected_rasis_of_the_planet(house_to_planet, planet_id)
        }
        house_from_lagna = (transit_sign - lagna_sign_d1) % 12 + 1
        house_from_venus = (transit_sign - natal_venus_sign) % 12 + 1
        flags[_planet_name(planet_id)] = {
            "sign": _sign_name_from_index(transit_sign),
            "house_from_lagna": int(house_from_lagna),
            "house_from_venus": int(house_from_venus),
            "occupies_1st_house_sign": transit_sign == natal_target_signs["1st_house_sign"],
            "occupies_5th_house_sign": transit_sign == natal_target_signs["5th_house_sign"],
            "occupies_7th_house_sign": transit_sign == natal_target_signs["7th_house_sign"],
            "occupies_venus_sign": transit_sign == natal_target_signs["venus_sign"],
            "aspects_1st_house_sign": natal_target_signs["1st_house_sign"] in aspected_signs,
            "aspects_5th_house_sign": natal_target_signs["5th_house_sign"] in aspected_signs,
            "aspects_7th_house_sign": natal_target_signs["7th_house_sign"] in aspected_signs,
            "aspects_venus_sign": natal_target_signs["venus_sign"] in aspected_signs,
        }
    return flags


def _yearly_relationship_transits(
    *,
    birth_input: BirthInput,
    place,
    lagna_sign_d1: int,
    d1_positions: list,
) -> dict:
    now = datetime.now(ZoneInfo(birth_input.timezone))
    natal_venus_sign = int(next(entry for entry in d1_positions[1:] if int(entry[0]) == jhora_const.VENUS_ID)[1][0])
    yearly_rows: list[dict] = []
    for year in range(now.year, now.year + 16):
        ref_jd = _jd_from_local_datetime(
            tz_name=birth_input.timezone,
            year=year,
            month=7,
            day=1,
            hour=12,
        )
        transit_positions = charts.divisional_chart(ref_jd, place, divisional_chart_factor=1)
        yearly_rows.append(
            {
                "year": year,
                "reference_date": {
                    "month": 7,
                    "day": 1,
                    "fractional_hour": 12.0,
                    "timezone": birth_input.timezone,
                },
                "major_planets": _relationship_target_flags(
                    transit_positions=transit_positions,
                    lagna_sign_d1=lagna_sign_d1,
                    natal_venus_sign=natal_venus_sign,
                ),
            }
        )
    return {
        "reference_method": "Yearly snapshot on July 1 at 12:00 local time.",
        "natal_reference": {
            "1st_house_sign": _sign_name_from_index(lagna_sign_d1),
            "5th_house_sign": _sign_name_from_index((lagna_sign_d1 + 4) % 12),
            "7th_house_sign": _sign_name_from_index((lagna_sign_d1 + 6) % 12),
            "venus_sign": _sign_name_from_index(natal_venus_sign),
        },
        "years": yearly_rows,
    }


def _vimshottari_summary(jd_birth: float, jd_now: float, place, d1_positions: list) -> dict:
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

    _, maha_rows_raw = vimsottari.get_vimsottari_dhasa_bhukthi(
        jd_birth,
        place,
        dhasa_level_index=jhora_const.MAHA_DHASA_DEPTH.MAHA_DHASA_ONLY,
    )
    _, antara_rows_raw = vimsottari.get_vimsottari_dhasa_bhukthi(
        jd_birth,
        place,
        dhasa_level_index=jhora_const.MAHA_DHASA_DEPTH.ANTARA,
    )
    _, praty_rows_raw = vimsottari.get_vimsottari_dhasa_bhukthi(
        jd_birth,
        place,
        dhasa_level_index=jhora_const.MAHA_DHASA_DEPTH.PRATYANTARA,
    )
    mahadasha_table = [_dasha_row_to_dict(lords, start, duration) for lords, start, duration in maha_rows_raw]
    antardasha_table = [_dasha_row_to_dict(lords, start, duration) for lords, start, duration in antara_rows_raw]
    pratyantardasha_table = [_dasha_row_to_dict(lords, start, duration) for lords, start, duration in praty_rows_raw]
    current_periods = {}
    current_names = [
        "mahadasha",
        "antardasha",
        "pratyantardasha",
    ]
    for period_name, row in zip(current_names, running):
        current_periods[period_name] = {
            "lords": [_planet_name_from_dasha_lord(lord) for lord in row[0]],
            "start": _gregorian_tuple_to_dict(row[1]),
            "end": _gregorian_tuple_to_dict(row[2]),
        }
    birth_balance = _birth_vimshottari_balance(jd_birth, place, d1_positions)

    return {
        **current_levels,
        "birth_balance": birth_balance,
        "as_of": {
            "julian_day": jd_now,
            "timezone": "same as birth input timezone for 'now'",
        },
        "sequence": sequence,
        "current_periods": current_periods,
        "mahadasha_table": mahadasha_table,
        "antardasha_table": antardasha_table,
        "pratyantardasha_table": pratyantardasha_table,
    }
