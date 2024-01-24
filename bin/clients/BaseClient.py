import queue
import logging

from threading import Timer

from prometheus_client import CollectorRegistry, Gauge

from common.consts import DEFAULT_MQTT_CLIENT_ID, CLIENT_METRICS, METRIC_STATUS, CLIENT_BASE
from models.MQTTConfigData import MQTTConfigurationData

_LOGGER = logging.getLogger(__name__)


class BaseClient:
    def __init__(self, client_name: str, version: str, registry: CollectorRegistry, configfile: str):
        self.client_name = client_name
        self._version = version
        self._registry = registry
        self._configfile = configfile
        self.is_connected = False
        self.is_running = True
        self._timer_listen: Timer | None = None
        self._timer_connect: Timer | None = None
        self._incoming_events = None
        self.outgoing_events = queue.Queue()

        self._metric_prefix = DEFAULT_MQTT_CLIENT_ID.lower()

        self._base_metrics_config = CLIENT_METRICS.get(CLIENT_BASE)
        self._base_metric_labels = self._base_metrics_config.get("labels")
        self._base_metrics = self._base_metrics_config.get("metrics")

        self._metrics_config = CLIENT_METRICS.get(client_name)
        self._client_metrics = self._metrics_config.get("metrics")
        self._client_metric_labels = self._metrics_config.get("labels")

        self._metric_labels = [*self._base_metric_labels, *self._client_metric_labels]

        self._metrics = {}

        self._build_metrics(self._base_metrics, self._base_metric_labels)
        self._build_metrics(self._client_metrics, self._metric_labels)

        mqtt_config = MQTTConfigurationData(self._configfile)

        self._base_metric_label_values = [mqtt_config.client_id, version]

        self._set_status(False)

    @property
    def should_connect(self):
        return self.is_running and not self.is_connected

    def _build_metrics(self, metrics, metric_labels):
        for metric in metrics:
            metric_suffix = metrics.get(metric).lower().replace(" ", "_")
            metric_name = f"{self._metric_prefix}_{self.client_name.lower()}_{metric_suffix}"
            metric_description = f"{self.client_name} {metric}"

            _LOGGER.debug(f"Creating metric '{metric_name}', Name: {metric_description}, Labels: {metric_labels}")

            gauge = Gauge(metric_name, metric_description, metric_labels)

            self._metrics[metric] = gauge
            self._registry.register(gauge)

    def initialize(self, incoming_events: queue.Queue):
        _LOGGER.info(f"Initialize {self.client_name}Client")

        self._incoming_events = incoming_events

        self._timer_listen = Timer(1.0, self._listen)
        self._timer_listen.start()

        self.connect()

    def terminate(self):
        _LOGGER.info(f"Terminating {self.client_name}Client")

        self.is_connected = False
        self.is_running = False

        self.outgoing_events.empty()
        self.outgoing_events = None

    def connect(self):
        _LOGGER.info(f"Starting to connect {self.client_name}Client, Should connect: {self.should_connect}")

        if self.should_connect:
            self._timer_connect = Timer(1.0, self._connect)
            self._timer_connect.start()

    def _connect(self):
        if not self.is_running:
            self.terminate()

    def _listen(self):
        if self.is_running:
            data = self._incoming_events.get()

            if data is None:
                self.terminate()

            else:
                self._event_received(data)

                self._incoming_events.task_done()

                self._timer_listen = Timer(0, self._listen)
                self._timer_listen.start()

    def _event_received(self, data):
        _LOGGER.debug(f"{self.client_name}Client Event received, Data: {data}")

    def set_status_metrics(self):
        status = 1 if self.is_connected else 0
        metric = self._metrics.get(METRIC_STATUS)

        metric.labels(*self._base_metric_label_values).set(status)

    def set_message_metrics(self, name, tags: list[str]):
        try:
            metric = self._metrics.get(name)

            label_values = [*self._base_metric_label_values, *tags]

            metric.labels(*label_values).inc()

        except Exception as ex:
            _LOGGER.error(
                f"Failed to report messages metrics, "
                f"Name: {name}, "
                f"Tags: {tags}, "
                f"Error: {ex}"
            )

    def _set_status(self, is_connected: bool):
        self.is_connected = is_connected
        self.set_status_metrics()
