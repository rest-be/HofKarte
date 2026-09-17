"""Tests für die WebSocket-Verwaltungs-API des HofKarte-Panels (management.py)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hofkarte.const import DOMAIN
from custom_components.hofkarte.coordinator import HofKarteUpdateCoordinator
from custom_components.hofkarte.data_provider import HofladenDataProvider
from custom_components.hofkarte.management import (
    _get_coordinator,
    _serialize_hofladen,
    async_register_websocket_commands,
    ws_delete,
    ws_list,
    ws_save,
)
from custom_components.hofkarte.models import Hofladen, Oeffnungszeit


class _FakeConnection:
    """Leichtgewichtige Ersatz-Verbindung für WebSocket-Handler-Tests.

    Bildet nur das nach, was ``management.py`` tatsächlich verwendet:
    einen admin-berechtigten Benutzer sowie ``send_result``/``send_error``.
    """

    def __init__(self) -> None:
        self.user = SimpleNamespace(is_admin=True)
        self.results: list[tuple[Any, Any]] = []
        self.errors: list[tuple[Any, str, str]] = []

    def send_result(self, msg_id: Any, data: Any = None) -> None:
        self.results.append((msg_id, data))

    def send_error(self, msg_id: Any, code: str, message: str) -> None:
        self.errors.append((msg_id, code, message))


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="HofKarte", data={CONF_NAME: "HofKarte"}
    )
    entry.add_to_hass(hass)
    return entry


async def _setup_mit_coordinator(hass: HomeAssistant) -> HofKarteUpdateCoordinator:
    entry = _make_entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return hass.data[DOMAIN][entry.entry_id]


class _ReadOnlyFakeProvider(HofladenDataProvider):
    """Rein lesender Provider zum Testen des 'nicht unterstützt'-Pfads."""

    async def async_fetch_raw_hoflaeden(self) -> list[dict[str, Any]]:
        return [{"id": "hof-1", "name": "Hofladen Eins"}]


# ---------------------------------------------------------------------------
# _serialize_hofladen / _json_value
# ---------------------------------------------------------------------------


def test_serialize_hofladen_wandelt_verschachtelte_werte_in_json_typen_um() -> None:
    """Zeiten, Tupel und verschachtelte Dataclasses müssen JSON-serialisierbar
    werden (str/list/dict), nicht als Python-Objekte übrig bleiben."""
    from datetime import datetime, time, timezone

    hofladen = Hofladen(
        id="hof-1",
        name="Hofladen Eins",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
    )

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert serialisiert["id"] == "hof-1"
    assert isinstance(serialisiert["oeffnungszeiten"], list)
    erste_zeit = serialisiert["oeffnungszeiten"][0]
    assert erste_zeit["beginn"] == "08:00"
    assert erste_zeit["ende"] == "12:00"
    assert erste_zeit["wochentag"] == 1


def test_serialize_hofladen_zeiten_ohne_sekunden() -> None:
    """Regressionstest für den behobenen Sekunden-Bug: time.isoformat()
    liefert standardmässig 'hh:mm:ss' - die Detailansicht darf aber nur
    'hh:mm' anzeigen, da Öffnungszeiten ausschliesslich minutengenau
    erfasst werden."""
    from datetime import datetime, time, timezone

    hofladen = Hofladen(
        id="hof-2",
        name="Hofladen Zwei",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=3, beginn=time(7, 30), ende=time(18, 45)),
        ),
    )

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )
    zeit = serialisiert["oeffnungszeiten"][0]

    assert zeit["beginn"] == "07:30"
    assert zeit["ende"] == "18:45"
    assert ":" not in zeit["beginn"][5:]  # kein zweiter Doppelpunkt -> keine Sekunden


# ---------------------------------------------------------------------------
# geoeffnet (serverseitig berechneter Öffnungsstatus für die
# Kacheln-/Listenansicht, siehe Issue #1 - keine Duplikation der
# Berechnungslogik in JavaScript)
# ---------------------------------------------------------------------------


def test_serialize_hofladen_enthaelt_geoeffnet_true() -> None:
    from datetime import datetime, time, timezone

    hofladen = Hofladen(
        id="hof-3",
        name="Hofladen Drei",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
    )
    # Montag, 10 Uhr -> innerhalb des Intervalls.
    montag_10_uhr = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)

    serialisiert = _serialize_hofladen(hofladen, now=montag_10_uhr)

    assert serialisiert["geoeffnet"] is True


def test_serialize_hofladen_enthaelt_geoeffnet_false() -> None:
    from datetime import datetime, time, timezone

    hofladen = Hofladen(
        id="hof-4",
        name="Hofladen Vier",
        oeffnungszeiten=(
            Oeffnungszeit(wochentag=1, beginn=time(8, 0), ende=time(12, 0)),
        ),
    )
    # Montag, 14 Uhr -> ausserhalb des Intervalls.
    montag_14_uhr = datetime(2026, 1, 5, 14, 0, tzinfo=timezone.utc)

    serialisiert = _serialize_hofladen(hofladen, now=montag_14_uhr)

    assert serialisiert["geoeffnet"] is False


def test_serialize_hofladen_geoeffnet_none_ohne_oeffnungszeiten() -> None:
    """Ohne hinterlegte Öffnungszeiten muss 'geoeffnet' None ('unbekannt')
    sein, nicht fälschlich False ('geschlossen')."""
    from datetime import datetime, timezone

    hofladen = Hofladen(id="hof-5", name="Hofladen Fünf")

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    )

    assert serialisiert["geoeffnet"] is None


def test_serialize_hofladen_enthaelt_hauptbild_url() -> None:
    from datetime import datetime, timezone

    from custom_components.hofkarte.models import Bild

    hofladen = Hofladen(
        id="hof-6",
        name="Hofladen Sechs",
        bilder=(Bild(url="https://example.com/logo.png"),),
    )

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert serialisiert["hauptbild_url"] == "https://example.com/logo.png"


def test_serialize_hofladen_hauptbild_url_none_ohne_bilder() -> None:
    from datetime import datetime, timezone

    hofladen = Hofladen(id="hof-7", name="Hofladen Sieben")

    serialisiert = _serialize_hofladen(
        hofladen, now=datetime(2026, 1, 1, tzinfo=timezone.utc)
    )

    assert serialisiert["hauptbild_url"] is None


async def test_ws_list_liefert_geoeffnet_fuer_jeden_hofladen(
    hass: HomeAssistant,
) -> None:
    """End-zu-Ende: Der WebSocket-Befehl 'list' muss 'geoeffnet' für jeden
    Hofladen mitliefern, konsistent mit dem tatsächlichen Zustand des
    Binary Sensors 'Geöffnet'."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-a", "name": "Hofladen A"})

    connection = _FakeConnection()
    ws_list(hass, connection, {"id": 1, "type": "hofkarte/management/list"})

    _, ergebnis = connection.results[0]
    hoflaeden = ergebnis["hoflaeden"]
    assert len(hoflaeden) == 1
    # Ohne hinterlegte Öffnungszeiten ist der Status unbekannt.
    assert hoflaeden[0]["geoeffnet"] is None


async def test_ws_save_liefert_geoeffnet_im_rueckgabe_hofladen(
    hass: HomeAssistant,
) -> None:
    """Auch die Rückgabe von 'save' muss 'geoeffnet' enthalten, damit die
    Oberfläche eine einzelne Änderung ohne vollständigen Re-List
    aktualisieren kann."""
    await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 1,
            "type": "hofkarte/management/save",
            "hofladen": {"id": "hof-b", "name": "Hofladen B"},
        },
    )
    await hass.async_block_till_done()

    _, ergebnis = connection.results[0]
    assert "geoeffnet" in ergebnis["hofladen"]


# ---------------------------------------------------------------------------
# _get_coordinator
# ---------------------------------------------------------------------------


def test_get_coordinator_wirft_fehler_wenn_nicht_eingerichtet(
    hass: HomeAssistant,
) -> None:
    """Ohne eingerichtete Config Entry muss ein klarer Fehler geworfen werden."""
    with pytest.raises(ValueError):
        _get_coordinator(hass)


# ---------------------------------------------------------------------------
# ws_list
# ---------------------------------------------------------------------------


async def test_ws_list_liefert_aktuelle_hoflaeden(hass: HomeAssistant) -> None:
    """ws_list muss alle aktuellen Hofläden serialisiert zurückgeben."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    connection = _FakeConnection()
    ws_list(hass, connection, {"id": 1, "type": "hofkarte/management/list"})

    assert len(connection.results) == 1
    msg_id, data = connection.results[0]
    assert msg_id == 1
    namen = [eintrag["name"] for eintrag in data["hoflaeden"]]
    assert "Hofladen Eins" in namen


# ---------------------------------------------------------------------------
# ws_save
# ---------------------------------------------------------------------------


async def test_ws_save_erstellt_neuen_hofladen_mit_generierter_id(
    hass: HomeAssistant,
) -> None:
    """Ohne 'id' im Rohdatensatz muss ws_save automatisch eine ID vergeben."""
    coordinator = await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 2,
            "type": "hofkarte/management/save",
            "hofladen": {"name": "Neuer Hofladen"},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 1
    msg_id, data = connection.results[0]
    assert msg_id == 2
    neue_id = data["hofladen"]["id"]
    assert neue_id.startswith("hofladen-")
    assert neue_id in coordinator.data
    assert coordinator.data[neue_id].name == "Neuer Hofladen"


async def test_ws_save_aktualisiert_bestehenden_hofladen(
    hass: HomeAssistant,
) -> None:
    """Mit bereits existierender 'id' muss ws_save den Hofladen aktualisieren
    statt einen Duplikat-Fehler zu erzeugen."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Alter Name"})

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 3,
            "type": "hofkarte/management/save",
            "hofladen": {"id": "hof-1", "name": "Neuer Name"},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    assert coordinator.data["hof-1"].name == "Neuer Name"


async def test_ws_save_ungueltige_daten_sendet_fehler(hass: HomeAssistant) -> None:
    """Ungültige Rohdaten (z. B. leerer Name) müssen als Fehler zurückgemeldet
    werden, ohne den Store zu verändern."""
    coordinator = await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 4,
            "type": "hofkarte/management/save",
            "hofladen": {"name": ""},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 4
    assert code == "invalid_data"
    assert coordinator.data == {}


# ---------------------------------------------------------------------------
# ws_delete
# ---------------------------------------------------------------------------


async def test_ws_delete_entfernt_hofladen(hass: HomeAssistant) -> None:
    """ws_delete muss einen bestehenden Hofladen dauerhaft entfernen."""
    coordinator = await _setup_mit_coordinator(hass)
    await coordinator.async_add_hofladen({"id": "hof-1", "name": "Hofladen Eins"})

    connection = _FakeConnection()
    ws_delete(
        hass,
        connection,
        {
            "id": 5,
            "type": "hofkarte/management/delete",
            "hofladen_id": "hof-1",
        },
    )
    await hass.async_block_till_done()

    assert len(connection.errors) == 0
    assert len(connection.results) == 1
    assert "hof-1" not in coordinator.data


async def test_ws_delete_unbekannte_id_sendet_not_found_fehler(
    hass: HomeAssistant,
) -> None:
    """Eine nicht existierende ID muss einen 'not_found'-Fehler ergeben."""
    await _setup_mit_coordinator(hass)

    connection = _FakeConnection()
    ws_delete(
        hass,
        connection,
        {
            "id": 6,
            "type": "hofkarte/management/delete",
            "hofladen_id": "unbekannt",
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 6
    assert code == "not_found"


async def test_ws_delete_nicht_unterstuetzt_bei_read_only_provider(
    hass: HomeAssistant,
) -> None:
    """Ein rein lesender Provider muss einen 'not_supported'-Fehler ergeben."""
    provider = _ReadOnlyFakeProvider()
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["fake-entry"] = coordinator

    connection = _FakeConnection()
    ws_delete(
        hass,
        connection,
        {
            "id": 7,
            "type": "hofkarte/management/delete",
            "hofladen_id": "hof-1",
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 7
    assert code == "not_supported"


# ---------------------------------------------------------------------------
# async_register_websocket_commands
# ---------------------------------------------------------------------------


async def test_async_register_websocket_commands_registriert_alle_drei(
    hass: HomeAssistant,
) -> None:
    """Alle drei WebSocket-Befehle müssen registriert werden."""
    async_register_websocket_commands(hass)

    ws_handlers = hass.data.get("websocket_api", {})
    assert "hofkarte/management/list" in ws_handlers
    assert "hofkarte/management/save" in ws_handlers
    assert "hofkarte/management/delete" in ws_handlers


# ---------------------------------------------------------------------------
# Fehlerbehandlung: HofKarte nicht (mehr) eingerichtet
# ---------------------------------------------------------------------------


def test_ws_list_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    """Ohne eingerichtetes HofKarte darf keine unbehandelte ValueError aus
    dem WebSocket-Handler entkommen – ein sauberer Fehler muss zurückkommen."""
    connection = _FakeConnection()

    ws_list(hass, connection, {"id": 10, "type": "hofkarte/management/list"})

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 10
    assert code == "not_ready"


async def test_ws_save_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()

    ws_save(
        hass,
        connection,
        {
            "id": 11,
            "type": "hofkarte/management/save",
            "hofladen": {"name": "Hofladen"},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 11
    assert code == "not_ready"


async def test_ws_delete_ohne_eingerichtete_integration_sendet_fehler(
    hass: HomeAssistant,
) -> None:
    connection = _FakeConnection()

    ws_delete(
        hass,
        connection,
        {"id": 12, "type": "hofkarte/management/delete", "hofladen_id": "hof-1"},
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 12
    assert code == "not_ready"


async def test_ws_save_nicht_unterstuetzt_ergibt_eigenen_fehlercode(
    hass: HomeAssistant,
) -> None:
    """Ein nicht schreibfähiger Provider muss als 'not_supported' gemeldet
    werden, nicht als 'invalid_data' (Fehlerarten klar unterscheiden)."""
    provider = _ReadOnlyFakeProvider()
    coordinator = HofKarteUpdateCoordinator(hass, provider)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["fake-entry"] = coordinator

    connection = _FakeConnection()
    ws_save(
        hass,
        connection,
        {
            "id": 13,
            "type": "hofkarte/management/save",
            "hofladen": {"id": "hof-neu", "name": "Neuer Hofladen"},
        },
    )
    await hass.async_block_till_done()

    assert len(connection.results) == 0
    assert len(connection.errors) == 1
    msg_id, code, _message = connection.errors[0]
    assert msg_id == 13
    assert code == "not_supported"


async def test_management_greift_nicht_mehr_direkt_auf_provider_zu() -> None:
    """Qualitätssicherung: management.py darf nicht mehr über
    ``coordinator._provider`` auf den Data Provider zugreifen (Kapselung
    über die öffentliche Coordinator-API)."""
    import inspect

    from custom_components.hofkarte import management

    quelltext = inspect.getsource(management)
    assert "coordinator._provider" not in quelltext
    assert "._provider" not in quelltext

