import sys
sys.path.append("/opt/loxberry/bin/plugins/vto2mqtt/clients/")

from Snapshot import Snapshot

configfile="/opt/loxberry/config/plugins/vto2mqtt/config.json"
_snap = Snapshot(configfile)
response = _snap.test_snapshots()
print(response)