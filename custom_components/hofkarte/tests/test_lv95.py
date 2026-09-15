"""Tests für lv95.py – Konvertierung WGS84 <-> LV95."""

from __future__ import annotations

import pytest

from custom_components.hofkarte.lv95 import (
    is_valid_lv95,
    lv95_to_wgs84,
    wgs84_to_lv95,
)

# Amtlicher swisstopo-Referenzpunkt "Wabern" (siehe swisstopo,
# "Die Koordinatensysteme in der Praxis"):
# LV95 E=2'600'980 / N=1'197'450 <-> ca. WGS84 46.9281°N, 7.4515°E
_REF_EASTING = 2600980.0
_REF_NORTHING = 1197450.0
_REF_LAT = 46.9281
_REF_LON = 7.4515

# Bern Bundesplatz (bereits an anderer Stelle im Projekt als Testpunkt
# verwendet, siehe test_end_to_end.py) – nahe dem LV95-Nullpunkt.
_BERN_LAT = 46.9480
_BERN_LON = 7.4474


def test_lv95_to_wgs84_amtlicher_referenzpunkt() -> None:
    """Die Rückrechnung des amtlichen Referenzpunkts muss auf wenige
    Meter genau mit den amtlichen WGS84-Werten übereinstimmen."""
    lat, lon = lv95_to_wgs84(_REF_EASTING, _REF_NORTHING)

    assert lat == pytest.approx(_REF_LAT, abs=0.0001)  # ca. 11 m Toleranz
    assert lon == pytest.approx(_REF_LON, abs=0.0001)


def test_wgs84_to_lv95_amtlicher_referenzpunkt() -> None:
    """Die Hinrechnung des amtlichen Referenzpunkts muss auf wenige Meter
    genau mit den amtlichen LV95-Werten übereinstimmen."""
    easting, northing = wgs84_to_lv95(_REF_LAT, _REF_LON)

    assert easting == pytest.approx(_REF_EASTING, abs=10)
    assert northing == pytest.approx(_REF_NORTHING, abs=10)


def test_rundreise_wgs84_lv95_wgs84_ist_verlustfrei() -> None:
    """Eine Hin- und Rückkonvertierung darf praktisch keine Abweichung
    einführen (wichtig: keine schleichende Drift bei wiederholtem
    Bearbeiten/Speichern in der Verwaltungsoberfläche)."""
    easting, northing = wgs84_to_lv95(_BERN_LAT, _BERN_LON)
    lat_zurueck, lon_zurueck = lv95_to_wgs84(easting, northing)

    assert lat_zurueck == pytest.approx(_BERN_LAT, abs=1e-5)
    assert lon_zurueck == pytest.approx(_BERN_LON, abs=1e-5)


def test_rundreise_lv95_wgs84_lv95_ist_verlustfrei() -> None:
    """Die Näherungsformeln sind keine exakten Umkehrfunktionen
    voneinander (unabhängig gefittete Polynome) – eine Rundreise darf
    aber nur eine für die Praxis vernachlässigbare Restabweichung von
    deutlich unter einem Meter aufweisen."""
    lat, lon = lv95_to_wgs84(_REF_EASTING, _REF_NORTHING)
    easting_zurueck, northing_zurueck = wgs84_to_lv95(lat, lon)

    assert easting_zurueck == pytest.approx(_REF_EASTING, abs=1.0)
    assert northing_zurueck == pytest.approx(_REF_NORTHING, abs=1.0)


def test_bern_liegt_nahe_beim_lv95_nullpunkt() -> None:
    """Der LV95-Nullpunkt (2'600'000 / 1'200'000) liegt bei der alten
    Sternwarte Bern - ein Punkt in der Berner Innenstadt muss daher nahe
    bei diesen Werten liegen (Plausibilitätsprüfung)."""
    easting, northing = wgs84_to_lv95(_BERN_LAT, _BERN_LON)

    assert 2_590_000 < easting < 2_610_000
    assert 1_190_000 < northing < 1_210_000


def test_is_valid_lv95_akzeptiert_schweizer_koordinaten() -> None:
    assert is_valid_lv95(_REF_EASTING, _REF_NORTHING) is True


def test_is_valid_lv95_lehnt_wgs84_werte_ab() -> None:
    """Werden versehentlich WGS84-Dezimalgrad als LV95 eingegeben (z. B.
    46.9, 7.4 statt 2'600'980, 1'197'450), muss das erkannt werden."""
    assert is_valid_lv95(46.9, 7.4) is False


def test_is_valid_lv95_lehnt_vertauschte_werte_ab() -> None:
    """Easting und Northing vertauscht (typischer Bedienfehler) muss
    ausserhalb der Bounding Box liegen und erkannt werden."""
    # Northing-Wertebereich (~1'075'000-1'296'000) als Easting eingesetzt.
    assert is_valid_lv95(1_197_450.0, 2_600_980.0) is False


def test_is_valid_lv95_lehnt_ausland_ab() -> None:
    assert is_valid_lv95(0.0, 0.0) is False
    assert is_valid_lv95(3_000_000.0, 1_200_000.0) is False


# ---------------------------------------------------------------------------
# End-zu-End: LV95-Eingabe -> Speicherung als WGS84 -> Anzeige als LV95
# ---------------------------------------------------------------------------


async def test_lv95_workflow_end_zu_ende_ueber_echten_coordinator(hass) -> None:
    """Simuliert exakt das, was das JS-Panel tut: LV95-Eingabe lokal nach
    WGS84 umrechnen, über den bestehenden Coordinator/Backend-Vertrag
    speichern (unverändertes latitude/longitude-Feld), und beim erneuten
    Laden wieder nach LV95 zurückrechnen. Stellt sicher, dass die
    GUI-Änderung ohne jede Backend-/Datenmodell-Änderung funktioniert."""
    from homeassistant.const import CONF_NAME
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.hofkarte.const import DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Nutzer gibt LV95-Koordinaten des swisstopo-Referenzpunkts ein;
    # das Panel rechnet lokal nach WGS84 um, bevor gespeichert wird.
    lat_eingabe, lon_eingabe = lv95_to_wgs84(_REF_EASTING, _REF_NORTHING)

    hofladen = await coordinator.async_add_hofladen(
        {
            "id": "hof-lv95-test",
            "name": "LV95-Testhofladen",
            "latitude": lat_eingabe,
            "longitude": lon_eingabe,
        }
    )

    # Unverändert über die bestehende WGS84-Speicherung abrufbar ...
    gespeichert = coordinator.data["hof-lv95-test"]
    assert gespeichert.latitude == pytest.approx(lat_eingabe)
    assert gespeichert.longitude == pytest.approx(lon_eingabe)

    # ... und beim Anzeigen wieder in LV95 zurückrechenbar, ohne
    # nennenswerten Drift gegenüber der ursprünglichen Eingabe.
    easting_zurueck, northing_zurueck = wgs84_to_lv95(
        gespeichert.latitude, gespeichert.longitude
    )
    assert easting_zurueck == pytest.approx(_REF_EASTING, abs=1.0)
    assert northing_zurueck == pytest.approx(_REF_NORTHING, abs=1.0)
    assert hofladen.id == "hof-lv95-test"
