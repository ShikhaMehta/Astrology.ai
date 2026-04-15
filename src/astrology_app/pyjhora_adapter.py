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
from jhora.horoscope.chart import charts
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


def generate_pyjhora_chart_package(birth_input: BirthInput) -> dict:
    jhora_const._DEFAULT_AYANAMSA_MODE = "LAHIRI"

    lat, lon = _geocode(birth_input.birth_place)
    tz_hours = _timezone_offset_hours_at_birth(
        birth_input.timezone,
        birth_input.date_of_birth,
        birth_input.time_of_birth,
    )
    place = drik.Place(birth_input.birth_place, lat, lon, tz_hours)

    y, m, d = _parse_ymd(birth_input.date_of_birth)
    hh, mm = _parse_hm(birth_input.time_of_birth)
    jd = _julian_day_number((y, m, d), (hh, mm, 0))

    d1 = charts.divisional_chart(
        jd, place, divisional_chart_factor=1, chart_method=1
    )
    d9 = charts.divisional_chart(
        jd, place, divisional_chart_factor=9, chart_method=1
    )

    lagna_sign_d1 = int(d1[0][1][0])
    chart_d1 = _serialize_chart(d1, lagna_sign_d1, include_nakshatra_pada=True)
    lagna_sign_d9 = int(d9[0][1][0])
    chart_d9 = _serialize_chart(d9, lagna_sign_d9, include_nakshatra_pada=False)

    nakshatras = _nakshatras_from_d1(d1)

    jd_now = _now_jd_same_convention(birth_input.timezone)
    dashas = _vimshottari_summary(jd, jd_now, place)

    return {
        "source": "pyjhora-adapter",
        "input": asdict(birth_input),
        "metadata": {
            "ayanamsha_mode": "LAHIRI",
            "dasha_system": "vimshottari",
            "charts_included": ["d1", "d9"],
            "status": "computed",
            "resolved_location": {
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "timezone_offset_hours": tz_hours,
            },
        },
        "charts": {"d1": chart_d1, "d9": chart_d9},
        "dashas": dashas,
        "nakshatras": nakshatras,
        "notes": [
            "Computed with PyJHora (jhora) divisional_chart and Vimśottari routines.",
            "Birth time is interpreted as local civil time in the resolved IANA timezone.",
            "Place coordinates come from OpenStreetMap/Nominatim geocoding of the birth place string.",
        ],
    }


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
        pid = entry[0]
        sgn, lon = entry[1]
        sgn = int(sgn)
        pname = PLANET_NAMES[int(pid)]
        house = (sgn - lagna_sign) % 12 + 1
        planet_data: dict = {
            "sign": SIGN_NAMES[sgn],
            "longitude_in_sign_degrees": round(float(lon), 4),
            "house": house,
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
        sgn, lon = entry[1]
        full_long = (int(sgn) * 30.0 + float(lon)) % 360.0
        nkk, pd, _ = drik.nakshatra_pada(full_long)
        by_planet[PLANET_NAMES[pid]] = {
            "name": NAKSHATRA_NAMES[int(nkk) - 1],
            "pada": int(pd),
        }
    return {
        "moon": {"name": NAKSHATRA_NAMES[int(nk) - 1], "pada": int(pada)},
        "by_planet": by_planet,
    }


def _planet_name_from_dasha_lord(lord: int) -> str:
    if isinstance(lord, int):
        return PLANET_NAMES.get(lord, str(lord))
    return str(lord)


def _vimshottari_summary(jd_birth: float, jd_now: float, place) -> dict:
    running = vimsottari.get_running_dhasa_for_given_date(
        jd_now,
        jd_birth,
        place,
        dhasa_level_index=jhora_const.MAHA_DHASA_DEPTH.ANTARA,
    )
    if len(running) < 2:
        raise RuntimeError("Unexpected Vimśottari depth result from PyJHora.")
    maha_row, antara_row = running[0], running[1]
    maha_lords = maha_row[0]
    antara_lords = antara_row[0]
    maha_id = maha_lords[0] if isinstance(maha_lords, tuple) else maha_lords
    if isinstance(antara_lords, tuple) and len(antara_lords) >= 2:
        bhukti_id = antara_lords[1]
    else:
        bhukti_id = antara_lords

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
        "current_mahadasha": _planet_name_from_dasha_lord(int(maha_id)),
        "current_antardasha": _planet_name_from_dasha_lord(int(bhukti_id)),
        "as_of": {
            "julian_day": jd_now,
            "timezone": "same as birth input timezone for 'now'",
        },
        "sequence": sequence,
    }
