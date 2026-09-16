"""Parsing und Validierung roher Hofladen-Daten.

Dieses Modul trennt bewusst Rohdaten (``Mapping``/``dict``) von der internen,
typisierten Darstellung in ``models.py``. Die produktive Datenquelle ist der
integrationsinterne Home-Assistant-Storage, der über den Data Provider
kapselt wird. Das Parsing kennt bewusst keine konkrete Speicher- oder
Persistenzimplementierung und erwartet lediglich ein einfaches,
JSON-kompatibles Mapping je Hofladen.

Ungültige oder unvollständige Pflichtdaten führen zu einer
:class:`HofladenValidationError` mit einer für Menschen verständlichen
Fehlermeldung. Fehlende optionale Felder werden robust auf ``None`` bzw.
leere Sammlungen abgebildet.

Intervall-Regel für ``beginn``/``ende`` (Öffnungszeit und
Sonderöffnungszeit): ``ende == beginn`` ist ungültig (nicht definierbare
Dauer). ``ende < beginn`` ist hingegen gültig und bedeutet ein Intervall,
das die Mitternacht überschreitet (z. B. 22:00–02:00) – siehe
``opening_hours.py`` für die Berechnung anhand solcher Intervalle.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, time
from typing import Any

from .models import (
    Angebot,
    Bild,
    Hofladen,
    Merkmal,
    Oeffnungszeit,
    Sonderoeffnungszeit,
    Verkaufsart,
    Zahlungsart,
)

_LATITUDE_MIN = -90.0
_LATITUDE_MAX = 90.0
_LONGITUDE_MIN = -180.0
_LONGITUDE_MAX = 180.0
_WOCHENTAG_MIN = 1
_WOCHENTAG_MAX = 7


class HofladenValidationError(ValueError):
    """Rohdaten für einen Hofladen sind ungültig oder unvollständig."""


def _require_str(raw: Mapping[str, Any], field_name: str) -> str:
    value = raw.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise HofladenValidationError(
            f"Pflichtfeld '{field_name}' fehlt oder ist leer."
        )
    return value.strip()


def _optional_str(raw: Mapping[str, Any], field_name: str) -> str | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise HofladenValidationError(
            f"Feld '{field_name}' muss eine Zeichenkette sein."
        )
    stripped = value.strip()
    return stripped or None


def _optional_float(
    raw: Mapping[str, Any], field_name: str, minimum: float, maximum: float
) -> float | None:
    value = raw.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HofladenValidationError(f"Feld '{field_name}' muss eine Zahl sein.")
    number = float(value)
    if not minimum <= number <= maximum:
        raise HofladenValidationError(
            f"Feld '{field_name}' muss zwischen {minimum} und {maximum} liegen."
        )
    return number


def _parse_time(raw_value: Any, context: str, field_name: str) -> time:
    if isinstance(raw_value, time):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return time.fromisoformat(raw_value)
        except ValueError as err:
            raise HofladenValidationError(
                f"{context}: ungültige Uhrzeit in '{field_name}': '{raw_value}'."
            ) from err
    raise HofladenValidationError(
        f"{context}: ungültige Uhrzeit in '{field_name}': {raw_value!r}."
    )


def _parse_date(raw_value: Any, context: str, field_name: str) -> date:
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        try:
            return date.fromisoformat(raw_value)
        except ValueError as err:
            raise HofladenValidationError(
                f"{context}: ungültiges Datum in '{field_name}': '{raw_value}'."
            ) from err
    raise HofladenValidationError(
        f"{context}: ungültiges Datum in '{field_name}': {raw_value!r}."
    )


def _parse_oeffnungszeit(raw: Any, index: int) -> Oeffnungszeit:
    context = f"Öffnungszeit #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    wochentag = raw.get("wochentag")
    if (
        not isinstance(wochentag, int)
        or isinstance(wochentag, bool)
        or not (_WOCHENTAG_MIN <= wochentag <= _WOCHENTAG_MAX)
    ):
        raise HofladenValidationError(
            f"{context}: 'wochentag' muss zwischen {_WOCHENTAG_MIN} (Montag) "
            f"und {_WOCHENTAG_MAX} (Sonntag) liegen."
        )

    beginn = _parse_time(raw.get("beginn"), context, "beginn")
    ende = _parse_time(raw.get("ende"), context, "ende")
    if ende == beginn:
        raise HofladenValidationError(
            f"{context}: 'ende' darf nicht gleich 'beginn' sein."
        )

    return Oeffnungszeit(wochentag=wochentag, beginn=beginn, ende=ende)


def _parse_sonderoeffnungszeit(raw: Any, index: int) -> Sonderoeffnungszeit:
    context = f"Sonderöffnungszeit #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    datum_von = _parse_date(raw.get("datum_von"), context, "datum_von")
    datum_bis = _parse_date(raw.get("datum_bis"), context, "datum_bis")
    if datum_bis < datum_von:
        raise HofladenValidationError(
            f"{context}: 'datum_bis' darf nicht vor 'datum_von' liegen."
        )

    geschlossen = bool(raw.get("geschlossen", False))

    beginn: time | None = None
    ende: time | None = None
    if not geschlossen:
        if raw.get("beginn") is None or raw.get("ende") is None:
            raise HofladenValidationError(
                f"{context}: 'beginn' und 'ende' sind erforderlich, solange "
                "'geschlossen' nicht gesetzt ist."
            )
        beginn = _parse_time(raw["beginn"], context, "beginn")
        ende = _parse_time(raw["ende"], context, "ende")
        if ende == beginn:
            raise HofladenValidationError(
                f"{context}: 'ende' darf nicht gleich 'beginn' sein."
            )

    return Sonderoeffnungszeit(
        datum_von=datum_von,
        datum_bis=datum_bis,
        geschlossen=geschlossen,
        beginn=beginn,
        ende=ende,
    )


def _parse_lookup(raw: Any, index: int, kind: str, factory: Any) -> Any:
    context = f"{kind} #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    id_value = raw.get("id")
    name_value = raw.get("name")
    if not isinstance(id_value, str) or not id_value.strip():
        raise HofladenValidationError(f"{context}: 'id' fehlt oder ist leer.")
    if not isinstance(name_value, str) or not name_value.strip():
        raise HofladenValidationError(f"{context}: 'name' fehlt oder ist leer.")

    return factory(id=id_value.strip(), name=name_value.strip())


def _parse_angebot(raw: Any, index: int) -> Angebot:
    context = f"Angebot #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    id_value = raw.get("id")
    name_value = raw.get("name")
    if not isinstance(id_value, str) or not id_value.strip():
        raise HofladenValidationError(f"{context}: 'id' fehlt oder ist leer.")
    if not isinstance(name_value, str) or not name_value.strip():
        raise HofladenValidationError(f"{context}: 'name' fehlt oder ist leer.")

    gruppen_raw = raw.get("gruppen", []) or []
    if not isinstance(gruppen_raw, (list, tuple)):
        raise HofladenValidationError(f"{context}: 'gruppen' muss eine Liste sein.")
    gruppen = tuple(
        str(gruppe).strip() for gruppe in gruppen_raw if str(gruppe).strip()
    )

    return Angebot(id=id_value.strip(), name=name_value.strip(), gruppen=gruppen)


def _migriere_kategorien_und_produkte_zu_angeboten(
    raw: Mapping[str, Any],
) -> list[Any]:
    """Migriert die frühere, getrennte Struktur (``kategorien``/``produkte``)
    verlustfrei in eine einheitliche Liste von Angebot-Rohdaten.

    **Idempotent:** Ist der Schlüssel ``angebote`` bereits vorhanden
    (neues Format), wird dieser unverändert zurückgegeben – die
    Migration greift ausschliesslich, wenn ausschliesslich die alten
    Schlüssel ``kategorien``/``produkte`` vorhanden sind. Ein bereits
    migrierter Datensatz wird durch erneutes Einlesen also nicht
    nochmals verändert.

    Jedes bestehende Produkt wird zu einem Angebot; seine
    ``kategorie_ids`` werden anhand der bestehenden ``kategorien``-Liste
    zu Gruppen-**Namen** aufgelöst (unbekannte IDs bleiben als rohe ID
    erhalten statt die Zuordnung stillschweigend zu verwerfen, analog
    zum bisherigen Verhalten in ``attributes.py``). Kategorien ohne
    zugeordnete Produkte („verwaiste“ Kategorien) werden als
    eigenständige Angebote mit leeren ``gruppen`` erhalten, damit ihr
    Name nicht stillschweigend verloren geht.
    """
    if "angebote" in raw:
        angebote_raw = raw.get("angebote") or []
        return list(angebote_raw) if isinstance(angebote_raw, (list, tuple)) else []

    kategorien_raw = raw.get("kategorien") or []
    produkte_raw = raw.get("produkte") or []
    if not kategorien_raw and not produkte_raw:
        return []

    kategorie_namen_je_id: dict[str, str] = {}
    if isinstance(kategorien_raw, (list, tuple)):
        for kategorie in kategorien_raw:
            if isinstance(kategorie, Mapping):
                kid, kname = kategorie.get("id"), kategorie.get("name")
                if isinstance(kid, str) and isinstance(kname, str):
                    kategorie_namen_je_id[kid] = kname

    verwendete_kategorie_ids: set[str] = set()
    angebote: list[Any] = []

    if isinstance(produkte_raw, (list, tuple)):
        for produkt in produkte_raw:
            if not isinstance(produkt, Mapping):
                # Ungültig - unverändert weitergeben, _parse_angebot meldet
                # den konkreten Fehler (Fail-Fast bleibt erhalten).
                angebote.append(produkt)
                continue
            kategorie_ids = produkt.get("kategorie_ids") or []
            gruppen: list[str] = []
            if isinstance(kategorie_ids, (list, tuple)):
                for kategorie_id in kategorie_ids:
                    kategorie_id_str = str(kategorie_id)
                    verwendete_kategorie_ids.add(kategorie_id_str)
                    gruppen.append(
                        kategorie_namen_je_id.get(kategorie_id_str, kategorie_id_str)
                    )
            angebote.append(
                {
                    "id": produkt.get("id"),
                    "name": produkt.get("name"),
                    "gruppen": gruppen,
                }
            )

    if isinstance(kategorien_raw, (list, tuple)):
        for kategorie in kategorien_raw:
            if not isinstance(kategorie, Mapping):
                continue
            kategorie_id = kategorie.get("id")
            if kategorie_id is not None and str(kategorie_id) not in verwendete_kategorie_ids:
                angebote.append(
                    {"id": kategorie_id, "name": kategorie.get("name"), "gruppen": []}
                )

    return angebote


def _parse_bild(raw: Any, index: int) -> Bild:
    context = f"Bild #{index}"
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(f"{context}: muss ein Mapping (dict) sein.")

    url = raw.get("url")
    if not isinstance(url, str) or not url.strip():
        raise HofladenValidationError(f"{context}: 'url' fehlt oder ist leer.")

    beschreibung = raw.get("beschreibung")
    if beschreibung is not None and not isinstance(beschreibung, str):
        raise HofladenValidationError(
            f"{context}: 'beschreibung' muss eine Zeichenkette sein."
        )

    hochgeladen = raw.get("hochgeladen", False)
    if not isinstance(hochgeladen, bool):
        raise HofladenValidationError(f"{context}: 'hochgeladen' muss ein Bool sein.")

    return Bild(
        url=url.strip(),
        beschreibung=(beschreibung.strip() if beschreibung else None) or None,
        hochgeladen=hochgeladen,
    )


def _parse_list(raw: Mapping[str, Any], field_name: str, parse_item: Any) -> tuple:
    items = raw.get(field_name, []) or []
    if not isinstance(items, (list, tuple)):
        raise HofladenValidationError(f"Feld '{field_name}' muss eine Liste sein.")
    return tuple(parse_item(item, i) for i, item in enumerate(items))


def parse_hofladen(raw: Mapping[str, Any]) -> Hofladen:
    """Rohdaten eines Hofladens in das interne, typisierte Modell überführen.

    Erwartet ein Mapping mit mindestens den Pflichtfeldern ``id`` und
    ``name``. Alle übrigen Felder sind optional und werden bei Fehlen
    robust auf ``None`` bzw. eine leere Sammlung abgebildet.

    Wirft :class:`HofladenValidationError`, wenn Pflichtfelder fehlen oder
    Werte fachlich ungültig sind (z. B. Koordinaten ausserhalb des gültigen
    Bereichs, ein Öffnungszeit-Ende vor dem Beginn).
    """
    if not isinstance(raw, Mapping):
        raise HofladenValidationError(
            "Rohdaten eines Hofladens müssen ein Mapping (dict) sein."
        )

    hofladen_id = _require_str(raw, "id")
    name = _require_str(raw, "name")

    beschreibung = _optional_str(raw, "beschreibung")
    adresse = _optional_str(raw, "adresse")
    plz = _optional_str(raw, "plz")
    ort = _optional_str(raw, "ort")
    land = _optional_str(raw, "land")
    website = _optional_str(raw, "website")

    latitude = _optional_float(raw, "latitude", _LATITUDE_MIN, _LATITUDE_MAX)
    longitude = _optional_float(raw, "longitude", _LONGITUDE_MIN, _LONGITUDE_MAX)

    oeffnungszeiten = _parse_list(raw, "oeffnungszeiten", _parse_oeffnungszeit)
    sonderoeffnungszeiten = _parse_list(
        raw, "sonderoeffnungszeiten", _parse_sonderoeffnungszeit
    )
    angebote_raw = _migriere_kategorien_und_produkte_zu_angeboten(raw)
    angebote = tuple(
        _parse_angebot(item, i) for i, item in enumerate(angebote_raw)
    )
    zahlungsarten = _parse_list(
        raw,
        "zahlungsarten",
        lambda item, i: _parse_lookup(item, i, "Zahlungsart", Zahlungsart),
    )
    verkaufsarten = _parse_list(
        raw,
        "verkaufsarten",
        lambda item, i: _parse_lookup(item, i, "Verkaufsart", Verkaufsart),
    )
    merkmale = _parse_list(
        raw, "merkmale", lambda item, i: _parse_lookup(item, i, "Merkmal", Merkmal)
    )
    bilder = _parse_list(raw, "bilder", _parse_bild)

    return Hofladen(
        id=hofladen_id,
        name=name,
        beschreibung=beschreibung,
        adresse=adresse,
        plz=plz,
        ort=ort,
        land=land,
        website=website,
        latitude=latitude,
        longitude=longitude,
        oeffnungszeiten=oeffnungszeiten,
        sonderoeffnungszeiten=sonderoeffnungszeiten,
        angebote=angebote,
        zahlungsarten=zahlungsarten,
        verkaufsarten=verkaufsarten,
        merkmale=merkmale,
        bilder=bilder,
    )
