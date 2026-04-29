from enum import StrEnum


class DahuaRPC(StrEnum):
    CONSOLE_RUN_CMD = "console.runCmd"
    LOGIN = "global.login"
    KEEPALIVE = "global.keepAlive"
    EVENT_MANAGER_ATTACH = "eventManager.attach"
    GET_SOFTWARE_VERSION = "magicBox.getSoftwareVersion"
    GET_DEVICE_TYPE = "magicBox.getDeviceType"
    GET_SYSTEM_INFO_NEW = "magicBox.getSystemInfoNew"
    GET_CONFIG = "configManager.getConfig"
    OPEN_DOOR = "accessControl.openDoor"
    ACCESS_CONTROL_FACTORY_INSTANCE = "accessControl.factory.instance"
    SYSTEM_MULTI_CALL = "system.multicall"
    REBOOT = "magicBox.reboot"
    EVENT_STREAM = "client.notifyEventStream"
    GET_SERIAL_NUMBER = "magicBox.getSerialNo"
    GET_BOOT_PARAMETER = "magicBox.getBootParameter"
    GET_PRODUCT_DEFINITION = "magicBox.getProductDefinition"
    GET_PROCESS_INFO = "magicBox.getProcessInfo"
    GENERAL_FACTORY_INSTANCE = "magicBox.factory.instance"
    GET_DEVICE_CLASS = "magicBox.getDeviceClass"
    GET_SUB_MODULES = "magicBox.getSubModules"


class DahuaConfig(StrEnum):
    ACCESS_CONTROL = "AccessControl"


class ClientType(StrEnum):
    DAHUA = "Dahua"
    MQTT = "MQTT"
    BASE = "Base"


class MetricType(StrEnum):
    MQTT_INCOMING_MESSAGES = "Incoming Messages"
    MQTT_OUTGOING_MESSAGES = "Outgoing Messages"
    MQTT_FAILED_OUTGOING_MESSAGES = "Failed Outgoing Messages"

    DAHUA_MESSAGES = "Messages"
    DAHUA_FAILED_MESSAGES = "Failed Messages"

    CONNECTIVITY_STATUS = "Connectivity Status"


class DeviceCommand(StrEnum):
    OPEN_DOOR = "Open"
    MUTE = "Mute"
