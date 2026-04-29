import asyncio
import json
import logging
import os
import sys
from time import sleep

from prometheus_client import CollectorRegistry

from clients.BaseClient import BaseClient
from clients.DahuaAPI import DahuaAPI
from common.consts import CLIENT_DAHUA
from models.DahuaDevice import DahuaDevice

_LOGGER = logging.getLogger(__name__)

DAHUA_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "dahua_config.json")


class DahuaClient(BaseClient):
    def __init__(self, version: str, registry: CollectorRegistry, configfile: str):
        super().__init__(CLIENT_DAHUA, version, registry, configfile)

        self._configfile = configfile
        self.api: DahuaAPI | None = None

        # Load device from user config
        with open(configfile) as f:
            pcfg = json.load(f)
        self._device = DahuaDevice.load_from_config(pcfg.get("dahuaConfigData", {}))

        # Load RPC endpoint config
        with open(DAHUA_CONFIG_FILE) as f:
            dahua_cfg = json.load(f)
        self._rpc_endpoints = dahua_cfg.get("endpoints", {})

    def _set_api(self, api: DahuaAPI):
        self.api = api

    def _connect(self):
        super(DahuaClient, self)._connect()

        while not self.is_connected:
            sleep_time = 5

            try:
                _LOGGER.info("Connecting")

                loop = asyncio.new_event_loop()

                client = loop.create_connection(
                    lambda: DahuaAPI(
                                self.outgoing_events,
                                self._device,
                                self._rpc_endpoints,
                                self._set_api,
                                self._set_status,
                                self.set_message_metrics
                    ),
                    self._device.hostname,
                    self._device.port
                )

                transport, protocol = loop.run_until_complete(client)

                try:
                    loop.run_forever()
                finally:
                    # Ensure transport is closed before closing the loop
                    if transport is not None and not transport.is_closing():
                        transport.close()
                    # Give the loop a moment to process the close
                    loop.run_until_complete(loop.shutdown_asyncgens())
                    loop.close()

            except Exception as ex:
                self._set_status(False)

                exc_type, exc_obj, exc_tb = sys.exc_info()
                line = exc_tb.tb_lineno

                _LOGGER.error(f"Connection failed, Error: {ex}, Line: {line}")

                sleep_time = 30

            finally:
                _LOGGER.info(f"Disconnected, will try to connect in {sleep_time} seconds")

                self._set_status(False)

                sleep(sleep_time)

    def _event_received(self, data):
        super(DahuaClient, self)._event_received(data)

        topic = data.get("topic")
        payload = data.get("payload")

        if self.api is None:
            _LOGGER.warning(f"Dropping command before Dahua API is ready, Topic: {topic}, Payload: {payload}")
            return

        self.api.execute_command(topic, payload)
