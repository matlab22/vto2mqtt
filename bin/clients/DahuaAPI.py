import asyncio
from collections.abc import Callable
from copy import copy
import json
import logging
import queue
import sys
from threading import Timer
from typing import Optional

from common.consts import (
    CONCAT_ACTION_MESSAGE,
    DAHUA_DEVICE_TYPE,
    DAHUA_SERIAL_NUMBER,
    MAX_MESSAGES_IN_BULK,
)
from common.enums import DahuaRPC, DeviceCommand, MetricType
from common.utils import convert_message, get_hashed_password
from models.DahuaDevice import DahuaDevice

LOGIN_TIMEOUT_SECONDS = 30

_LOGGER = logging.getLogger(__name__)


class DahuaAPI(asyncio.Protocol):
    def __init__(self,
                 outgoing_events: queue.Queue,
                 device: DahuaDevice,
                 rpc_endpoints: dict,
                 set_api,
                 set_status,
                 set_message_metrics):

        super().__init__()

        self._device = device
        self._rpc_endpoints = rpc_endpoints

        self._realm = None
        self._random = None
        self._request_id = 1
        self._session_id = 0
        self._keep_alive_interval = 0
        self._transport = None

        self._commands = {
            DeviceCommand.OPEN_DOOR: self._access_control_open_door,
            DeviceCommand.MUTE: self._run_cmd_mute
        }

        self._rpc_handlers: dict[str, Callable[[dict], None]] = {
            DahuaRPC.LOGIN: self._handle_authenticate,
            DahuaRPC.EVENT_STREAM: self._handle_attach_event_manager,
            DahuaRPC.GET_SOFTWARE_VERSION: self._handle_generic_config_data,
            DahuaRPC.GET_DEVICE_TYPE: self._handle_generic_config_data,
            DahuaRPC.ACCESS_CONTROL_FACTORY_INSTANCE: self._handle_generic_config_data,
            DahuaRPC.GET_CONFIG: self._handle_config_data,
            DahuaRPC.SYSTEM_MULTI_CALL: self._process_multiple,
            DahuaRPC.GET_SYSTEM_INFO_NEW: self._handle_generic_config_data,
            DahuaRPC.GET_SERIAL_NUMBER: self._handle_generic_config_data,
            DahuaRPC.KEEPALIVE: self._handle_keep_alive
        }

        self._message_extenders: dict[DahuaRPC, Callable[[dict], None]] = {
            DahuaRPC.OPEN_DOOR: self._extend_access_control_message
        }

        self._request_queue: dict[int, dict] = {}

        self._rx_buffer = bytearray()
        self._keep_alive_timer: Optional[Timer] = None
        self._login_timeout_timer: Optional[Timer] = None

        self._loop = asyncio.get_event_loop()
        self._outgoing_events = outgoing_events
        self._set_status = set_status
        self._set_message_metrics = set_message_metrics
        self._session_password = None

        self._can_publish = False
        self._pending_delivery_items: list[dict] = []

        set_api(self)

    def execute_command(self, topic: str, payload: dict):
        try:
            device_command = DeviceCommand(topic)

            if device_command in self._commands:
                command = self._commands[device_command]
                command(payload)
            else:
                _LOGGER.warning(f"No command available for {topic}, Payload: {payload}")

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(f"Failed to execute command, Error: {ex}, Line: {exc_tb.tb_lineno}")

    def connection_made(self, transport):
        _LOGGER.debug("Connection established")

        try:
            self._transport = transport
            self._authenticate()

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(f"Connection failed, unable to reconnect, error: {ex}, Line: {exc_tb.tb_lineno}")

    def data_received(self, data):
        try:
            _LOGGER.debug(f"Received data, Raw Data: {data}")

            self._rx_buffer.extend(data)

            for message in self._extract_messages():
                try:
                    self._process(message)
                except Exception as ex:
                    exc_type, exc_obj, exc_tb = sys.exc_info()
                    _LOGGER.error(
                        f"Failed to dispatch message, "
                        f"Message: {message}, "
                        f"Error: {ex}, "
                        f"Line: {exc_tb.tb_lineno}"
                    )
                    self._set_message_metrics(MetricType.DAHUA_FAILED_MESSAGES, [self._session_id, "incoming"])

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(
                f"Failed to handle message, "
                f"Data: {data}, "
                f"Error: {ex}, "
                f"Line: {exc_tb.tb_lineno}"
            )
            self._set_message_metrics(MetricType.DAHUA_FAILED_MESSAGES, [self._session_id, "incoming"])

    def _extract_messages(self):
        """Yield complete JSON messages from the rx buffer.

        Dahua DHIP wraps each JSON payload in a 32-byte binary header,
        but TCP can split a single payload across multiple ``data_received``
        calls. Rather than trusting the header's length field (which varies
        between firmwares), we scan the buffer for balanced top-level JSON
        objects and yield each one as it becomes complete. Anything before
        the next ``{`` (DHIP header bytes, etc.) is discarded.
        """
        while True:
            start = self._rx_buffer.find(b'{')
            if start < 0:
                self._rx_buffer.clear()
                return

            if start > 0:
                del self._rx_buffer[:start]

            depth = 0
            in_string = False
            escape = False
            end = -1

            for i, b in enumerate(self._rx_buffer):
                ch = chr(b)

                if escape:
                    escape = False
                    continue

                if in_string:
                    if ch == '\\':
                        escape = True
                    elif ch == '"':
                        in_string = False
                    continue

                if ch == '"':
                    in_string = True
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break

            if end < 0:
                return

            payload = bytes(self._rx_buffer[:end + 1])
            del self._rx_buffer[:end + 1]

            try:
                yield json.loads(payload.decode('utf-8', errors='replace'))
            except Exception as ex:
                _LOGGER.error(
                    f"Failed to parse JSON message, "
                    f"Data: {payload}, "
                    f"Error: {ex}"
                )
                self._set_message_metrics(MetricType.DAHUA_FAILED_MESSAGES, [self._session_id, "incoming"])

    def _cancel_timers(self):
        if self._keep_alive_timer is not None:
            self._keep_alive_timer.cancel()
            self._keep_alive_timer = None
        if self._login_timeout_timer is not None:
            self._login_timeout_timer.cancel()
            self._login_timeout_timer = None

    def _close_transport(self):
        if self._transport is not None and not self._transport.is_closing():
            self._transport.close()

    def eof_received(self):
        _LOGGER.info('Server sent EOF message')

        self._cancel_timers()
        self._close_transport()
        self._loop.stop()

    def connection_lost(self, exc):
        _LOGGER.error(f'Server closed the connection, exc: {exc}')

        self._cancel_timers()
        self._close_transport()
        self._loop.stop()

    def _send(self, endpoint: DahuaRPC, additional_params: dict | None = None):
        message_data = self._get_message(endpoint, additional_params)
        self._send_internal(message_data)

    def _send_multiple(self, requests: list[dict]):
        requests_left = copy(requests)

        while len(requests_left) > 0:
            requests_to_process = requests_left[:MAX_MESSAGES_IN_BULK]
            requests_left = requests_left[MAX_MESSAGES_IN_BULK:]

            message_data = self._get_messages(requests_to_process)
            self._send_internal(message_data)

    def _send_internal(self, message_data: dict):
        _LOGGER.debug(f"Sending message, Data: {message_data}")

        if not self._transport.is_closing():
            message = convert_message(message_data)
            self._transport.write(message)

    def _add_listener(self, endpoint: DahuaRPC, params: dict | list):
        message_id = self._request_id

        self._request_queue[message_id] = {
            "endpoint": endpoint,
            "params": params
        }

        self._set_message_metrics(MetricType.DAHUA_MESSAGES, [self._session_id, endpoint])

    def _get_messages(self, requests: list[dict]) -> dict:
        params = []

        for request in requests:
            endpoint_name = request.get("name")
            request_params: dict | None = request.get("params")

            endpoint = DahuaRPC(endpoint_name)
            message = self._get_message(endpoint, request_params)
            params.append(message)

        self._request_id += 1

        message_data = {
            "id": self._request_id,
            "session": self._session_id,
            "method": str(DahuaRPC.SYSTEM_MULTI_CALL),
            "params": params
        }

        self._add_listener(DahuaRPC.SYSTEM_MULTI_CALL, params)

        return message_data

    def _get_message(self, endpoint: DahuaRPC, additional_params: dict | None = None) -> dict:
        params = {}

        if endpoint in self._rpc_endpoints:
            endpoint_config = self._rpc_endpoints[endpoint]
            endpoint_params = endpoint_config.get("overrideParams")

            if endpoint_params is not None:
                params = copy(endpoint_params)

        if additional_params is not None:
            params.update(additional_params)

        self._request_id += 1

        message_data = {
            "id": self._request_id,
            "session": self._session_id,
            "magic": "0x1234",
            "method": str(endpoint),
            "params": params
        }

        if endpoint in self._message_extenders:
            extend_data = self._message_extenders.get(endpoint)
            extend_data(message_data)

        self._add_listener(endpoint, params)

        return message_data

    def _on_login_timeout(self):
        _LOGGER.error(f"Login did not complete within {LOGIN_TIMEOUT_SECONDS}s, forcing disconnect")
        self._cancel_timers()
        self._close_transport()
        self._loop.stop()

    def _authenticate(self):
        _LOGGER.debug("Prepare login message")

        # Start login timeout on first auth attempt
        if self._session_password is None:
            self._login_timeout_timer = Timer(LOGIN_TIMEOUT_SECONDS, self._on_login_timeout)
            self._login_timeout_timer.daemon = True
            self._login_timeout_timer.start()

        additional_params = {
            "userName": self._device.username
        }

        if self._session_password is not None:
            additional_params["password"] = self._session_password
            additional_params["authorityType"] = "Default"

        self._send(DahuaRPC.LOGIN, additional_params)

    def _process(self, message):
        try:
            if message is not None:
                message_id = message.get("id")
                method = message.get("method")

                if message_id in self._request_queue:
                    request_data = self._request_queue.get(message_id)
                    endpoint = request_data.get("endpoint")

                    _LOGGER.debug(f"Processing message #{message_id}, Endpoint: {endpoint}, Message: {message}")

                    rpc_handler = self._rpc_handlers.get(endpoint)

                    if rpc_handler is not None:
                        rpc_handler(message)

                    del self._request_queue[message_id]

                elif method == DahuaRPC.EVENT_STREAM:
                    rpc_handler = self._rpc_handlers.get(method)

                    if rpc_handler is not None:
                        rpc_handler(message)
                else:
                    _LOGGER.warning(
                        f"Cannot process message #{message_id}, "
                        f"No handler registered, Message: {message}"
                    )

                _LOGGER.debug(f"Message #{message_id} handled")

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(
                f"Failed to process message, "
                f"Data: {message}, "
                f"Error: {ex}, "
                f"Line: {exc_tb.tb_lineno}"
            )

    def _handle_authenticate(self, message):
        try:
            error = message.get("error", {})
            params = message.get("params")

            if self._session_password is None:
                error_message = error.get("message")

                if error_message == "Component error: login challenge!":
                    self._random = params.get("random")
                    self._realm = params.get("realm")
                    self._session_id = message.get("session")

                    self._session_password = get_hashed_password(
                        self._random,
                        self._realm,
                        self._device.username,
                        self._device.password
                    )

                    self._authenticate()

            else:
                keep_alive_interval = params.get("keepAliveInterval")

                if keep_alive_interval is not None:
                    # Login succeeded - cancel login timeout
                    if self._login_timeout_timer is not None:
                        self._login_timeout_timer.cancel()
                        self._login_timeout_timer = None

                    self._set_status(True)
                    self._keep_alive_interval = keep_alive_interval - 5

                    self._handle_keep_alive()
                    self._load_device()

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(
                f"Failed to authenticate, "
                f"Data: {message}, "
                f"Error: {ex}, "
                f"Line: {exc_tb.tb_lineno}"
            )

    def _extend_access_control_message(self, message_data: dict) -> None:
        if self._device.access_control_token is not None:
            message_data["object"] = self._device.access_control_token

    def _load_device(self):
        try:
            endpoints = {
                endpoint: self._rpc_endpoints[endpoint]
                for endpoint in self._rpc_endpoints
                if self._rpc_endpoints[endpoint].get("isDeviceDetails", False)
            }

            for endpoint in endpoints:
                endpoint_config = endpoints[endpoint]
                params = endpoint_config.get("overrideParams")

                if endpoint_config is not None:
                    sub_params = endpoint_config.get("subParams")

                    if sub_params is None:
                        self._send(endpoint, params)
                    else:
                        if MAX_MESSAGES_IN_BULK > 1:
                            requests = []
                            for method_data_item in sub_params:
                                item_params = copy(params) if params else {}
                                item_params.update(method_data_item)
                                request = {
                                    "name": endpoint,
                                    "params": item_params
                                }
                                requests.append(request)
                            self._send_multiple(requests)
                        else:
                            for method_data_item in sub_params:
                                item_params = copy(params) if params else {}
                                item_params.update(method_data_item)
                                self._send(endpoint, item_params)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(
                f"Failed to load device, "
                f"Error: {ex}, "
                f"Line: {exc_tb.tb_lineno}"
            )

    def _process_multiple(self, message):
        try:
            message_params = message.get("params")

            for message_item in message_params:
                self._process(message_item)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(
                f"Failed to handle multiple messages, "
                f"Data: {message}, "
                f"Error: {ex}, "
                f"Line: {exc_tb.tb_lineno}"
            )

    def _handle_config_data(self, message):
        try:
            error = message.get("error")

            if error is None:
                message_id = message.get("id")
                request_data = self._request_queue.get(message_id)

                endpoint_name = request_data.get("endpoint")
                request_params = request_data.get("params")
                sub_param = request_params.get("name")

                endpoint = DahuaRPC(endpoint_name)
                params = message.get("params")

                self._update_device(endpoint, params, sub_param)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(
                f"Failed to handle configuration data, "
                f"Data: {message}, "
                f"Error: {ex}, "
                f"Line: {exc_tb.tb_lineno}"
            )

    def _handle_generic_config_data(self, message):
        try:
            message_id = message.get("id")
            request_data = self._request_queue.get(message_id)

            endpoint_name = request_data.get("endpoint")
            endpoint = DahuaRPC(endpoint_name)

            error = message.get("error")

            if error is None:
                params = message.get("params")

                if endpoint == DahuaRPC.ACCESS_CONTROL_FACTORY_INSTANCE:
                    params = {
                        "instance": message.get("result")
                    }

                self._update_device(endpoint, params)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(
                f"Failed to handle generic configuration data, "
                f"Data: {message}, "
                f"Error: {ex}, "
                f"Line: {exc_tb.tb_lineno}"
            )

    def _update_device(self, endpoint: DahuaRPC, data: dict | str, sub_param: str | None = None):
        self._device.update(endpoint, data, sub_param)

        event = endpoint if sub_param is None else f"{endpoint}/{sub_param}"
        self._publish_outgoing_event(f"Device/{event}", data)

    def _publish_pending_events(self):
        for item in self._pending_delivery_items:
            event = item.get("event")
            payload = item.get("payload")
            self._publish_outgoing_event(event, payload)

        self._pending_delivery_items.clear()

    def _publish_outgoing_event(self, event: str, payload: dict):
        if not self._can_publish:
            if None in [self._device.type, self._device.serial_number]:
                self._pending_delivery_items.append({
                    "event": event,
                    "payload": payload
                })
                return
            else:
                self._can_publish = True
                self._publish_pending_events()

        payload[DAHUA_DEVICE_TYPE] = self._device.type
        payload[DAHUA_SERIAL_NUMBER] = self._device.serial_number

        event_data = {
            "event": event,
            "payload": payload
        }

        self._outgoing_events.put(event_data)

    def _handle_attach_event_manager(self, message):
        try:
            method = message.get("method")
            params = message.get("params")

            if method == DahuaRPC.EVENT_STREAM:
                event_list = params.get("eventList")

                for event_message in event_list:
                    code = event_message.get("Code")
                    self._publish_outgoing_event(f"{code}/Event", event_message)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(f"Failed to handle event, error: {ex}, Line: {exc_tb.tb_lineno}")

    def _keep_alive(self):
        _LOGGER.debug("Keep alive")

        additional_params = {
            "timeout": self._keep_alive_interval,
            "action": True
        }

        self._send(DahuaRPC.KEEPALIVE, additional_params)

    def _handle_keep_alive(self, _message=None):
        _LOGGER.debug(f"Set timer for {self._keep_alive_interval} seconds to trigger keep alive message")

        self._keep_alive_timer = Timer(self._keep_alive_interval, self._keep_alive)
        self._keep_alive_timer.daemon = True
        self._keep_alive_timer.start()

    def _run_cmd_mute(self, _payload: dict):
        _LOGGER.debug("Mute call")

        request_data = {
            "command": "hc"
        }

        self._send(DahuaRPC.CONSOLE_RUN_CMD, request_data)

    def _access_control_open_door(self, payload: dict):
        door_id = payload.get("Door", 1)

        is_locked = self._device.is_locked(door_id)
        should_unlock = False

        try:
            if is_locked:
                _LOGGER.info(f"Access Control - Door #{door_id} is already unlocked, ignoring request")
            else:
                is_locked = True
                should_unlock = True

                self._device.set_lock(door_id, is_locked)
                self._publish_lock_state(door_id, False)

                request_data = {
                    "DoorIndex": door_id,
                    "Type": "",
                    "UserID": "",
                }

                self._send(DahuaRPC.OPEN_DOOR, request_data)

        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            _LOGGER.error(f"Failed to open door, error: {ex}, Line: {exc_tb.tb_lineno}")

        if should_unlock and is_locked:
            Timer(self._device.hold_time, self._magnetic_unlock, (self, door_id)).start()

    def _publish_lock_state(self, door_id: int, is_locked: bool):
        state = "Locked" if is_locked else "Unlocked"

        _LOGGER.info(f"Access Control - {state} magnetic lock #{door_id}")

        message = {
            "door": door_id,
            "isLocked": is_locked
        }

        self._publish_outgoing_event("MagneticLock/Status", message)

    @staticmethod
    def _magnetic_unlock(self, door_id):
        self._device.set_lock(door_id, False)
        self._publish_lock_state(door_id, True)
