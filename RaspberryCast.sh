#!/bin/bash

if [ $# -ne 1 ]; then
        echo "Error: This script takes exactly one argument."
        echo "The argument should be either 'start' or 'stop'."
        exit
fi

if [ $1 = "start" ]; then
	if [ `id -u` -eq 0 ]
	then
		echo "Please start this script without root privileges!"
		echo "Try again without sudo."
		exit 0
	fi
	echo "Checking for updates."
	git pull
	echo "Starting RaspberryCast server."
	python3 server.py &
	echo "Done."
	exit
elif [ $1 = "stop" ] ; then
	if [ `id -u` -ne 0 ]
	then
		echo "Please start this script with root privileges!"
		echo "Try again with sudo."
		exit 0
	fi
	echo "Killing RaspberryCast..."
	killall omxplayer.bin >/dev/null 2>&1
	killall python3 >/dev/null 2>&1
	kill $(lsof -t -i :2020) >/dev/null 2>&1
	rm *.srt >/dev/null 2>&1
	echo "Done."
	exit
else
	echo "Error, illegal argument. Possible values are: 'stop', 'start'."
	exit
fi
