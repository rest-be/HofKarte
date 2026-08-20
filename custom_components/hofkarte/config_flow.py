"""Config Flow für die HofKarte-Integration.

Die Integration wird ausschliesslich über die Home-Assistant-Oberfläche
eingerichtet. Eine YAML-Konfiguration ist bewusst nicht vorgesehen.

Architekturhinweis (offene Entscheidung):
Die eigentliche Hofladen-Datenquelle steht zum Zeitpunkt dieser Einheit noch
nicht fest (z. B. lokale Verwaltung durch den Benutzer vs. externer Dienst).
Um keine erfundene externe API anzunehmen, beschränkt sich der Config Flow
in dieser Einheit auf eine klar begrenzte, sinnvolle Konfigurationsstruktur:
einen Anzeigenamen für die Integrationsinstanz. HofKarte wird als
Single-Instance-Integration behandelt, da sie eine zentrale, HA-weite
Kartenverwaltung darstellt und nicht pro Hofladen einzeln eingerichtet wird.
Die konkrete Datenquelle für Hofläden ist Gegenstand einer späteren
Architekturentscheidung (siehe Einheit 3 – Fachliches Datenmodell und
Data Layer).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME

from .const import DEFAULT_NAME, DOMAIN


def _normalize_name(raw_name: str) -> str:
    """Whitespace am Rand entfernen und mehrfache Leerzeichen reduzieren."""
    return " ".join(raw_name.split())


class HofKarteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Flow für HofKarte."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einzigen Einrichtungsschritt der Integration behandeln."""
        # HofKarte ist eine Single-Instance-Integration: es gibt genau eine
        # zentrale Kartenverwaltung pro Home-Assistant-Installation.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            name = _normalize_name(user_input[CONF_NAME])

            if not name:
                errors[CONF_NAME] = "invalid_name"
            else:
                return self.async_create_entry(
                    title=name,
                    data={CONF_NAME: name},
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=(user_input or {}).get(CONF_NAME, DEFAULT_NAME),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
