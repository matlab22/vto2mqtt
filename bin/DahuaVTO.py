#!/usr/bin/env python3

import os
import sys
import logging
import asyncio
import getopt
import json
from datetime import datetime
from time import sleep

from clients.DahuaClient import DahuaClient
from clients.MQTTClient import MQTTClient

# ======================
##
# Mapping Loglevel from loxberry log to python logging
##

def map_loglevel(loxlevel):
    switcher={
        0:logging.NOTSET,
        3:logging.ERROR,
        4:logging.WARNING,
        6:logging.INFO,
        7:logging.DEBUG
    }
    return switcher.get(int(loxlevel),"unsupported loglevel")

# ======================
##
# handle start arguments
##
inputs = None
outputs = None
loglevel=logging.ERROR
logfile=""
logfileArg = ""
lbhomedir = ""
configfile = ""
opts, args = getopt.getopt(sys.argv[1:], 'f:l:c:h:', ['logfile=', 'loglevel=', 'configfile=', 'lbhomedir='])
for opt, arg in opts:
    if opt in ('-f', '--logfile'):
        logfile=arg
        logfileArg = arg
    elif opt in ('-l', '--loglevel'):
        loglevel=map_loglevel(arg)
    elif opt in ('-c', '--configfile'):
        configfile=arg
    elif opt in ('-h', '--lbhomedir'):
        lbhomedir=arg

# ==============
##
# Setup logger function
##
def setup_logger(name):

    global loglevel
    global logfile

    logging.captureWarnings(1)
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()

    logger.addHandler(handler)
    logger.setLevel(loglevel)

    if not logfile:
        logfile="/tmp/"+datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')[:-3]+"_vto2mqtt.log"
    logging.basicConfig(filename=logfile,level=loglevel,format='%(asctime)s.%(msecs)03d <%(levelname)s> %(message)s',datefmt='%H:%M:%S')

    return logger

_LOGGER = setup_logger("VTO2MQTT")
_LOGGER.debug("logfile: " + logfileArg)
_LOGGER.info("loglevel: " + logging.getLevelName(_LOGGER.level))



class DahuaVTOManager:
    def __init__(self):
        try:
            with open(configfile) as json_pcfg_file:
                pcfg = json.load(json_pcfg_file)
                dahuaConfigData = pcfg['dahuaConfigData']
                # configure host ip
                self.host = str(dahuaConfigData['host']['ip'])
                _LOGGER.debug(f"Host IP: {self.host}")

        except Exception as e:
            _LOGGER.exception(str(e))
        self._mqtt_client = MQTTClient(configfile)
        self._dahua_client = DahuaClient(configfile)


    def initialize(self,configfile):
        self.configfile=configfile
        self._mqtt_client.initialize(self._dahua_client.outgoing_events)
        self._dahua_client.initialize(self._mqtt_client.outgoing_events)

        while True:
            sleep(1)


manager = DahuaVTOManager()
manager.initialize(configfile=configfile)
