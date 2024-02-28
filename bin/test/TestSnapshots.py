import sys
sys.path.append("/opt/loxberry/bin/plugins/vto2mqtt/clients/")  # Add the path to the 'clients' module

from Snapshot import Snapshot

def main():
    try:
        # Add your specific logic here
        configfile = "/opt/loxberry/config/plugins/vto2mqtt/config.json"
        _snap = Snapshot(configfile)
        response = _snap.test_snapshots()

        # Print the response
        print(f"Response: {response}")
    except Exception as e:
        # Handle exceptions and print an error message
        print(f'Script execution failed: {e}')

if __name__ == "__main__":
    main()
