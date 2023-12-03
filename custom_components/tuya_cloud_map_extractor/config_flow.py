from __future__ import annotations

import logging
from typing import Any
from .tuya_vacuum_map_extractor import (
    get_map,
    ClientIDError,
    ClientSecretError,
    DeviceIDError,
    ServerError,
)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import selector
from homeassistant.const import (
    CONF_NAME,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
)

import voluptuous as vol

from .const import (
    DOMAIN,
    CONF_SERVER,
    CONF_SERVER_CHINA,
    CONF_SERVER_WEST_AMERICA,
    CONF_SERVER_EAST_AMERICA,
    CONF_SERVER_CENTRAL_EUROPE,
    CONF_SERVER_WEST_EUROPE,
    CONF_SERVER_INDIA,
    CONF_COLORS,
    CONF_BG_COLOR,
    CONF_WALL_COLOR,
    CONF_INSIDE_COLOR,
    CONF_ROOM_COLORS,
    CONF_ROOM_COLOR,
    CONF_ROOM_NAME,
    DEFAULT_BG_COLOR,
    DEFAULT_ROOM_COLOR,
    DEFAULT_WALL_COLOR,
)

CONF_SERVERS = {
    CONF_SERVER_CHINA: "China",
    CONF_SERVER_WEST_AMERICA: "Western America",
    CONF_SERVER_EAST_AMERICA: "Eastern America",
    CONF_SERVER_CENTRAL_EUROPE: "Central Europe",
    CONF_SERVER_WEST_EUROPE: "Western Europe",
    CONF_SERVER_INDIA: "India"
}

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    def __init__(self) -> None:
        super().__init__()
        self.map_header = {}
        self._config_data = {}

    async def async_step_user(self, user_input=None):
        default_server = CONF_SERVER_CENTRAL_EUROPE
        default_name = "Vacuum map"
        default_client_id = ""
        default_client_secret = ""
        default_device_id = ""

        errors = {}
        if user_input is not None:
            try:
                headers, image = await validate(self.hass, user_input)
                self.map_header = headers
                if user_input[CONF_COLORS]:
                    del user_input[CONF_COLORS]
                    self._config_data.update(user_input)
                    return await self.async_step_colorconf()

                del user_input[CONF_COLORS]
                self._config_data.update(user_input)
                data = create_entry_data(
                    self._config_data.copy(), self.map_header.copy()
                )
                return self.async_create_entry(title=data.pop(CONF_NAME), data=data)

            except ClientIDError:
                errors[CONF_CLIENT_ID] = "client_id"
            except ClientSecretError:
                errors[CONF_CLIENT_SECRET] = "client_secret"
            except DeviceIDError:
                errors[CONF_DEVICE_ID] = "device_id"
            except ServerError:
                errors[CONF_SERVER] = "server"
            except Exception as error:
                _LOGGER.exception(error)
                errors["base"] = "unknown"

            default_name = user_input["name"]
            default_client_id = user_input["client_id"]
            default_client_secret = user_input["client_secret"]
            default_device_id = user_input["device_id"]
            default_server = user_input["server"]

        DATA_SCHEMA = {
            vol.Required(CONF_NAME, default=default_name): str,
            vol.Required(CONF_SERVER, default=default_server): vol.In(CONF_SERVERS),
            vol.Required(CONF_CLIENT_ID, default=default_client_id): str,
            vol.Required(CONF_CLIENT_SECRET, default=default_client_secret): str,
            vol.Required(CONF_DEVICE_ID, default=default_device_id): str,
            vol.Required(CONF_COLORS, default=False): bool,
        }

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(DATA_SCHEMA), errors=errors
        )

    async def async_step_colorconf(self, user_input=None):
        errors = {}
        if user_input is not None:
            if not CONF_BG_COLOR in user_input:
                user_input[CONF_BG_COLOR] = [0, 0, 0]
            if not CONF_WALL_COLOR in user_input:
                user_input[CONF_WALL_COLOR] = [0, 0, 0]

            if CONF_ROOM_COLORS in user_input:
                if user_input[CONF_ROOM_COLORS]:
                    del user_input[CONF_ROOM_COLORS]
                    self._config_data.update(user_input)
                    return await self.async_step_room_colors()
                else:
                    del user_input[CONF_ROOM_COLORS]
                    self._config_data.update(user_input)
                    data = create_entry_data(
                        self._config_data.copy(), self.map_header.copy()
                    )
                    return self.async_create_entry(title=data.pop(CONF_NAME), data=data)
            else:
                self._config_data.update(user_input)
                data = create_entry_data(
                    self._config_data.copy(), self.map_header.copy()
                )
                return self.async_create_entry(title=data.pop(CONF_NAME), data=data)

        DATA_SCHEMA = {
            CONF_BG_COLOR: selector(
                {"color_rgb": {}}  # TODO: default value of [44, 50, 64]
            ),
            CONF_WALL_COLOR: selector(
                {"color_rgb": {}}  # TODO: default value of [255, 255, 255]
            ),
        }

        if "roominfo" in self.map_header:
            DATA_SCHEMA[vol.Required(CONF_ROOM_COLORS, default=False)] = bool
        else:
            DATA_SCHEMA[CONF_INSIDE_COLOR] = selector({"color_rgb": {}})

        return self.async_show_form(
            step_id="colorconf", data_schema=vol.Schema(DATA_SCHEMA), errors=errors
        )

    async def async_step_room_colors(self, user_input=None):
        errors = {}
        rooms = self.map_header["roominfo"]
        DATA_SCHEMA = {}

        if user_input is not None:
            for i in rooms:
                if not (CONF_ROOM_COLOR + str(i["ID"])) in user_input:
                    user_input[CONF_ROOM_COLOR + str(i["ID"])] = [0, 0, 0]

            self._config_data.update(user_input)
            data = create_entry_data(self._config_data.copy(), self.map_header.copy())
            return self.async_create_entry(title=data.pop(CONF_NAME), data=data)

        for i in rooms:
            DATA_SCHEMA[
                vol.Required(CONF_ROOM_NAME + str(i["ID"]), default=i["name"])
            ] = str
            DATA_SCHEMA[CONF_ROOM_COLOR + str(i["ID"])] = selector({"color_rgb": {}})

        return self.async_show_form(
            step_id="room_colors", data_schema=vol.Schema(DATA_SCHEMA), errors=errors
        )


async def validate(hass: HomeAssistant, data: dict):
    """Validate the user input"""
    return await hass.async_add_executor_job(
        get_map,
        data["server"],
        data["client_id"],
        data["client_secret"],
        data["device_id"],
    )


def create_entry_data(data: dict, header: dict):
    roomless = not "roominfo" in header
    colors = {}

    if not roomless:
        rooms = header["roominfo"]

        if not (CONF_ROOM_COLOR + str(rooms[0]["ID"])) in data:
            for i in rooms:
                data[CONF_ROOM_COLOR + str(i["ID"])] = DEFAULT_ROOM_COLOR
        else:
            for i in rooms:
                del data[CONF_ROOM_NAME + str(i["ID"])]
        print(data)
        for i in rooms:
            colors[CONF_ROOM_COLOR + str(i["ID"])] = data.pop(
                CONF_ROOM_COLOR + str(i["ID"])
            )

    else:
        if CONF_INSIDE_COLOR not in data:
            data[CONF_INSIDE_COLOR] = DEFAULT_ROOM_COLOR
        colors[CONF_INSIDE_COLOR] = data.pop(CONF_INSIDE_COLOR)

    if not CONF_BG_COLOR in data:
        data[CONF_BG_COLOR] = DEFAULT_BG_COLOR
    if not CONF_WALL_COLOR in data:
        data[CONF_WALL_COLOR] = DEFAULT_WALL_COLOR

    colors[CONF_BG_COLOR] = data.pop(CONF_BG_COLOR)
    colors[CONF_WALL_COLOR] = data.pop(CONF_WALL_COLOR)

    data["colors"] = colors
    print(data)
    return data
