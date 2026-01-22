#!/bin/bash

PLUGINNAME=REPLACELBPPLUGINDIR
PATH="/sbin:/bin:/usr/sbin:/usr/bin:$LBHOMEDIR/bin:$LBHOMEDIR/sbin"

# Source environment variables
set -a
source /etc/environment
set +a

# Logfile
. $LBHOMEDIR/libs/bashlib/loxberry_log.sh
PACKAGE=${PLUGINNAME}
NAME=${PLUGINNAME}_MQTT
LOGDIR=$LBPLOG/${PLUGINNAME}



# Debug output
#STDERR=0
#DEBUG=0
if [[ ${LOGLEVEL} -eq 7 ]]; then
	LOGINF "Debugging is enabled! This will produce A LOT messages in your logfile!"
	STDERR=1
	DEBUG=1
fi

LOGSTART "vto2mqtt"

case "$1" in
  start|restart)

	#echo $HOSTNAME"/vto2mqtt/#" > $LBHOMEDIR/config/plugins/${PLUGINNAME}/mqtt_subscriptions.cfg
	
	if [ "$1" = "restart" ]; then
		LOGINF "Stopping vto2mqtt..."
		pkill -f "$LBHOMEDIR/bin/plugins/${PLUGINNAME}/DahuaVTO.py" >> ${FILENAME} 2>&1
	fi

	if [ "$(pgrep -f "$LBHOMEDIR/bin/plugins/${PLUGINNAME}/DahuaVTO.py")" ]; then
		LOGINF "DahuaVTO.py already running."
		LOGEND "vto2mqtt"
		exit 0
	fi

	LOGINF "Starting vto2mqtt..."
	$LBHOMEDIR/bin/plugins/${PLUGINNAME}/DahuaVTO.py \
  --logfile ${FILENAME} \
  --loglevel ${LOGLEVEL} \
  --configfile $LBHOMEDIR/config/plugins/${PLUGINNAME}/config.json \
  --lbhomedir $LBHOMEDIR >> ${FILENAME} 2>&1 &

	sleep 1
	if [ "$(pgrep -f "$LBHOMEDIR/bin/plugins/${PLUGINNAME}/DahuaVTO.py")" ]; then
		LOGOK "DahuaVTO.py started successfully."
	else
		LOGERR "DahuaVTO.py failed to start."
	fi

	LOGEND "vto2mqtt"
    exit 0
    ;;

  stop)

	LOGINF "Stopping vto2mqtt..."
	pkill -f "$LBHOMEDIR/bin/plugins/${PLUGINNAME}/DahuaVTO.py" >> ${FILENAME} 2>&1

	if [ "$(pgrep -f "$LBHOMEDIR/bin/plugins/${PLUGINNAME}/DahuaVTO.py")" ]; then
		LOGERR "DahuaVTO.py could not be stopped."
	else
		LOGOK "DahuaVTO.py stopped successfully."
	fi

	LOGEND "vto2mqtt"
        exit 0
        ;;

  *)
    echo "Usage: $0 [start|stop|restart]" >&2
	LOGINF "No command given. Exiting."
	LOGEND "vto2mqtt"
        exit 0
  ;;

esac

LOGEND "vto2mqtt"
