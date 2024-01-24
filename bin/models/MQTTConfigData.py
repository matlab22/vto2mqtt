import os
from typing import Optional, Dict

from common.consts import *
import json
import logging
_LOGGER = logging.getLogger(__name__)

class MQTTConfigurationData:
    host: Optional[str]
    username: Optional[str]
    password: Optional[str]
    port: Optional[int]
    topic_prefix: Optional[str]
    topic_command_prefix: Optional[str]
    configfile: Optional[str]

    def __init__(self,configfile):
        self.configfile=configfile
        try:
            with open(self.configfile) as json_pcfg_file:
                pcfg = json.load(json_pcfg_file)
                mqttConfigData = pcfg['mqttConfigData']
                # configure host ip
                self.client_id = str(mqttConfigData['client']['id'])

                self.host = str(mqttConfigData['server']['ip'])
                self.port = str(mqttConfigData['server']['port'])
                self.username = str(mqttConfigData['server']['username'])
                self.password = str(mqttConfigData['server']['password'])

                self.topic_prefix = str(mqttConfigData['client']['topic_prefix'])
                self.topic_command_prefix = f"{self.topic_prefix}{TOPIC_COMMAND}/"

                _LOGGER.debug(f"Client ID: {self.client_id}, MQTT Server: IP({self.host}), Port({self.port}), Username ({self.username}), Password({self.password})")

        except Exception as e:
            _LOGGER.exception(str(e))

