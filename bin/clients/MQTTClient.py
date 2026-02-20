import json
import logging
import sys
from time import sleep

import paho.mqtt.client as mqtt
from prometheus_client import CollectorRegistry

from clients.BaseClient import BaseClient
from common.consts import *
from models.MQTTConfigData import MQTTConfigurationData

from clients.Snapshot import Snapshot

_LOGGER = logging.getLogger(__name__)


class MQTTClient(BaseClient):
    configfile: str
    def __init__(self, version: str, registry: CollectorRegistry, configfile: str):
        super().__init__(CLIENT_MQTT, version, registry, configfile)

        self._mqtt_config = MQTTConfigurationData(configfile)
        
        # Support both paho-mqtt 1.x and 2.x
        try:
            # paho-mqtt 2.0+ requires callback_api_version
            self._mqtt_client = mqtt.Client(
                                            client_id=self._mqtt_config.client_id,
                                            clean_session=True,
                                            callback_api_version=mqtt.CallbackAPIVersion.VERSION1
                                        )
        except AttributeError:
            # paho-mqtt 1.x doesn't have callback_api_version
            self._mqtt_client = mqtt.Client(
                                            client_id=self._mqtt_config.client_id,
                                            clean_session=True
                                        )

        self._mqtt_client.user_data_set(self)
        self._mqtt_client.username_pw_set(self._mqtt_config.username, self._mqtt_config.password)

        self._mqtt_client.on_connect = self._on_mqtt_connect
        self._mqtt_client.on_message = self._on_mqtt_message
        self._mqtt_client.on_disconnect = self._on_mqtt_disconnect

        self._snap = Snapshot(configfile)

    @property
    def topic_command_prefix(self):
        return self._mqtt_config.topic_command_prefix

    @property
    def topic_prefix(self):
        return self._mqtt_config.topic_prefix

    def _connect(self):
        super(MQTTClient, self)._connect()

        self.set_status_metrics()

        config = self._mqtt_config

        while not self.is_connected:
            try:
                _LOGGER.info("MQTT Broker is trying to connect...")

                self._mqtt_client.connect(config.host, int(config.port), 60)
                self._mqtt_client.loop_start()

                sleep(5)

            except Exception as ex:
                exc_type, exc_obj, exc_tb = sys.exc_info()
                error_details = f"error: {ex}, Line: {exc_tb.tb_lineno}"

                _LOGGER.error(f"Failed to connect to broker, retry in 60 seconds, {error_details}")

                self.set_status_metrics()

                sleep(60)

    def _event_received(self, data):
        super(MQTTClient, self)._event_received(data)

        topic_suffix = data.get("event")
        payload = data.get("payload")

        topic = f"{self.topic_prefix}/{topic_suffix}"
        _LOGGER.debug(f"Publishing MQTT message {topic}: {payload}")

        try:
            self._snap.get_snapshot(current_topic_suffix=topic_suffix)
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(
                f"Failed to get snapshot, "
                f"Topic: {topic}, Payload: {payload}, "
                f"Error: {ex}, Line: {exc_tb.tb_lineno}"
            )

        try:
            self.set_message_metrics(METRIC_MQTT_OUTGOING_MESSAGES, [topic_suffix])

            self._mqtt_client.publish(topic, json.dumps(payload, indent=4))
        except Exception as ex:
            self.set_message_metrics(METRIC_MQTT_FAILED_OUTGOING_MESSAGES, [topic_suffix])

            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(
                f"Failed to publish message, "
                f"Topic: {topic}, Payload: {payload}, "
                f"Error: {ex}, Line: {exc_tb.tb_lineno}"
            )

    @staticmethod
    def _on_mqtt_connect(client, userdata, flags, rc):
        if rc == 0:
            _LOGGER.info(f"MQTT Broker connected with result code {rc}")

            client.subscribe(f"{userdata.topic_command_prefix}#")

            userdata.is_connected = True

            userdata.set_status_metrics()

        else:
            error_message = MQTT_ERROR_MESSAGES.get(rc, MQTT_ERROR_DEFAULT_MESSAGE)

            _LOGGER.error(f"MQTT Broker failed due to {error_message}")

            userdata.is_connected = False

            userdata.set_status_metrics()

            super(MQTTClient, userdata).connect()

    @staticmethod
    def _on_mqtt_message(client, userdata, msg):
        _LOGGER.debug(f"MQTT Message received, Topic: {msg.topic}, Payload: {msg.payload}")

        try:
            payload = {}

            if msg.payload is not None:
                data = msg.payload.decode("utf-8")

                if data is not None and len(data) > 0:
                    payload = json.loads(data)

            topic = msg.topic.replace(userdata.topic_command_prefix, "")

            event_data = {
                "topic": topic,
                "payload": payload
            }

            userdata.set_message_metrics(METRIC_MQTT_INCOMING_MESSAGES, [topic])

            userdata.outgoing_events.put(event_data)
        except Exception as ex:
            exc_type, exc_obj, exc_tb = sys.exc_info()

            _LOGGER.error(
                f"Failed to invoke handler, "
                f"Topic: {msg.topic}, Payload: {msg.payload}, "
                f"Error: {ex}, Line: {exc_tb.tb_lineno}"
            )

    @staticmethod
    def _on_mqtt_disconnect(client, userdata, rc):
        reason = MQTT_ERROR_MESSAGES.get(rc, MQTT_ERROR_DEFAULT_MESSAGE)

        _LOGGER.warning(f"MQTT Broker got disconnected, Reason Code: {rc} - {reason}")

        userdata.is_connected = False
        userdata.set_status_metrics()

        super(MQTTClient, userdata).connect()

