import os
from typing import Optional

from requests.auth import HTTPDigestAuth

from common.consts import *
import json
import logging
_LOGGER = logging.getLogger(__name__)

class DahuaConfigurationData:
    host: Optional[str]
    username: Optional[str]
    password: Optional[str]
    is_ssl: Optional[bool]
    auth: Optional[HTTPDigestAuth]


    def __init__(self, configfile: str):
        self.configfile=configfile
        try:
            with open(self.configfile) as json_pcfg_file:
                pcfg = json.load(json_pcfg_file)
                dahuaConfigData = pcfg['dahuaConfigData']
                # configure host ip
                self.host = str(dahuaConfigData['host']['ip'])
                self.is_ssl = str(os.environ.get('DAHUA_VTO_SSL', False)).lower() == str(True).lower()

                self.username = str(dahuaConfigData['host']['username'])
                self.password = str(dahuaConfigData['host']['password'])

                self._auth = HTTPDigestAuth(self.username, self.password)
                self._base_url = f"{PROTOCOLS[self.is_ssl]}://{self.host}/cgi-bin/"
                _LOGGER.debug(f"Host IP: {self.host}, Host Username: {self.username}, Host Password: {self.password}")

        except Exception as e:
            _LOGGER.exception(str(e))

        

    @property
    def base_url(self):
        return self._base_url

    @property
    def auth(self):
        return self._auth
