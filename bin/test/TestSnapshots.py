import sys
sys.path.append("/opt/loxberry/bin/plugins/vto2mqtt/clients/")  # Add the path to the 'clients' module

from Snapshot import Snapshot

def main():
    try:
        # Add your specific logic here
        configfile = "/opt/loxberry/config/plugins/vto2mqtt/config.json"
        _snap = Snapshot(configfile)
        response = _snap.test_snapshots()

        # Exit with success code
        sys.exit(0)
    except Exception as e:
        # Handle exceptions and print an error message
        print(f'Script execution failed: {e}', file=sys.stderr)
        # Exit with error code
        sys.exit(1)

if __name__ == "__main__":
    main()
