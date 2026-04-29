import logging
from typing import Optional

from requests.auth import HTTPDigestAuth

from common.consts import PROTOCOLS, DAHUA_DEVICE_TYPE, DAHUA_SERIAL_NUMBER
from common.enums import DahuaConfig, DahuaRPC

_LOGGER = logging.getLogger(__name__)


class DahuaDevice:
    hostname: Optional[str]
    port: int
    username: Optional[str]
    password: Optional[str]
    is_ssl: bool
    version: Optional[str]
    build_date: Optional[str]
    type: Optional[str]
    serial_number: Optional[str]
    access_control_token: Optional[int]
    hold_time: float

    def __init__(self, hostname: str, port: int, is_ssl: bool, username: str, password: str):
        self.hostname = hostname
        self.port = port
        self.is_ssl = is_ssl
        self.username = username
        self.password = password

        self.config: dict = {}
        self.version = None
        self.build_date = None
        self.type = None
        self.serial_number = None
        self.access_control_token = None
        self.hold_time = 0

        self._lock_status: dict[int, bool] = {}

        self._auth = HTTPDigestAuth(self.username, self.password)
        self._base_url = f"{PROTOCOLS[self.is_ssl]}://{self.hostname}:{self.port}/cgi-bin/"

        self._config_processors = {
            str(DahuaRPC.GET_DEVICE_TYPE): self._update_device_type,
            str(DahuaRPC.ACCESS_CONTROL_FACTORY_INSTANCE): self._update_access_control_factory_instance,
            str(DahuaRPC.GET_SOFTWARE_VERSION): self._update_version,
            str(DahuaRPC.GET_SERIAL_NUMBER): self._update_device_serial_number,
            f"{DahuaRPC.GET_CONFIG}|{DahuaConfig.ACCESS_CONTROL}": self._update_hold_time
        }

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def auth(self) -> HTTPDigestAuth:
        return self._auth

    def set_lock(self, door: int, state: bool) -> None:
        self._lock_status[door] = state

    def is_locked(self, door: int) -> bool:
        return self._lock_status.get(door, False)

    def update(self, endpoint: DahuaRPC, data: dict | str, sub_param: str | None = None):
        if sub_param is None:
            _LOGGER.debug(f"Set config item '{endpoint}', Data: {data}")
        else:
            _LOGGER.debug(f"Set config item '{endpoint}', Sub action: {sub_param}, Data: {data}")

        device_config = self.config.get(endpoint, {})
        config_id = str(endpoint)

        if sub_param is None:
            device_config.update(data)
        else:
            config_id = f"{config_id}|{sub_param}"
            sub_device_config = device_config.get(sub_param, {})
            sub_device_config.update(data)
            device_config[sub_param] = sub_device_config

        self.config[endpoint] = device_config

        if config_id in self._config_processors:
            process = self._config_processors[config_id]
            process(data)

    def _update_hold_time(self, data: dict):
        access_control_table = data.get("table", [])

        for item in access_control_table:
            access_control = item.get('AccessProtocol')

            if access_control == 'Local':
                hold_time = item.get('UnlockReloadInterval')
                self.hold_time = hold_time
                _LOGGER.info(f"Hold time: {self.hold_time}")

    def _update_version(self, data: dict):
        version_details = data.get("version", {})
        self.build_date = version_details.get("BuildDate")
        self.version = version_details.get("Version")

        _LOGGER.info(f"Version: {self.version}")
        _LOGGER.info(f"Build Date: {self.build_date}")

    def _update_device_type(self, data: dict):
        self.type = data.get("type")
        _LOGGER.info(f"Type: {self.type}")

    def _update_access_control_factory_instance(self, data: dict):
        self.access_control_token = data.get("instance")
        _LOGGER.info(f"Access Control Instance ID: {self.access_control_token}")

    def _update_device_serial_number(self, data: dict):
        self.serial_number = data.get("sn")
        _LOGGER.info(f"Serial Number: {self.serial_number}")

    @staticmethod
    def load_from_config(config: dict) -> "DahuaDevice":
        host_config = config.get("host", {})
        hostname = str(host_config.get("ip", ""))
        port = int(host_config.get("port", 5000))
        is_ssl = str(host_config.get("ssl", False)).lower() == "true"
        username = str(host_config.get("username", ""))
        password = str(host_config.get("password", ""))

        return DahuaDevice(hostname, port, is_ssl, username, password)
