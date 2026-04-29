DEFAULT_MQTT_CLIENT_ID = "DahuaVTO2MQTT"
DEFAULT_MQTT_TOPIC_PREFIX = "DahuaVTO"

PROTOCOLS = {
    True: "https",
    False: "http"
}

DAHUA_DEVICE_TYPE = "deviceType"
DAHUA_SERIAL_NUMBER = "serialNumber"

TOPIC_COMMAND = "/Command"

MAX_MESSAGES_IN_BULK = 10

PLACE_HOLDERS = ["{\"id\"", "{\"error\""]
UNICODE_APOSTROPHES = ["\u201c", "\u201d"]

CONCAT_ACTION_MESSAGE = {
    True: "Last chunk of opened stream",
    False: "Partial"
}

MQTT_ERROR_DEFAULT_MESSAGE = "Unknown error"

MQTT_ERROR_MESSAGES = {
    0: "MQTT Broker connected successfully",
    1: "Incorrect protocol version",
    2: "Invalid client identifier",
    3: "Server unavailable",
    4: "Bad username or password",
    5: "Not authorised",
    6: "Message not found (internal error)",
    7: "The connection was lost",
    8: "A TLS error occurred",
    9: "Payload too large",
    10: "This feature is not supported",
    11: "Authorisation failed",
    12: "Access denied by ACL",
    13: "Unknown error",
    14: "Error defined by errno",
    15: "Queue size",
}

CLIENT_DAHUA = "Dahua"
CLIENT_MQTT = "MQTT"
CLIENT_BASE = "Base"

METRIC_MQTT_INCOMING_MESSAGES = "Incoming Messages"
METRIC_MQTT_OUTGOING_MESSAGES = "Outgoing Messages"
METRIC_MQTT_FAILED_OUTGOING_MESSAGES = "Failed Outgoing Messages"

METRIC_DAHUA_MESSAGES = "Messages"
METRIC_DAHUA_FAILED_MESSAGES = "Failed Messages"

METRIC_STATUS = "Connectivity Status"

CLIENT_METRICS = {
    CLIENT_BASE: {
        "labels": ["instance", "version"],
        "metrics": {
            METRIC_STATUS: "status"
        }
    },
    CLIENT_DAHUA: {
        "labels": ["session_id", "topic"],
        "metrics": {
            METRIC_DAHUA_MESSAGES: METRIC_DAHUA_MESSAGES,
            METRIC_DAHUA_FAILED_MESSAGES: METRIC_DAHUA_FAILED_MESSAGES
        }
    },
    CLIENT_MQTT: {
        "labels": ["topic"],
        "metrics": {
            METRIC_MQTT_INCOMING_MESSAGES: METRIC_MQTT_INCOMING_MESSAGES,
            METRIC_MQTT_OUTGOING_MESSAGES: METRIC_MQTT_OUTGOING_MESSAGES,
            METRIC_MQTT_FAILED_OUTGOING_MESSAGES: METRIC_MQTT_FAILED_OUTGOING_MESSAGES
        }
    }
}
