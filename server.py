#!/usr/bin/env python

import logging, os, sys, json
with open('raspberrycast.conf') as f:    
    config = json.load(f)

#Setting log
logging.basicConfig(filename='RaspberryCast.log', format="%(asctime)s - %(levelname)s - %(message)s", datefmt='%m-%d %H:%M:%S', level=logging.DEBUG)
logger = logging.getLogger("RaspberryCast")

#Creating handler to print messages on stdout
root = logging.getLogger()
root.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

if config["new_log"]:
    os.system("sudo fbi -T 1 --noverbose -a  images/ready.jpg")

from bottle import *
from process import *
import urllib

setState("0")
open('video.queue', 'w').close() #Reset queue
logger.info('Server successfully started!')

app = Bottle()

SimpleTemplate.defaults["get_url"] = app.get_url

@app.hook('after_request')
def enable_cors():
    response.headers['Access-Control-Allow-Origin'] = '*'

@app.route('/static/<filename>', name='static')
def server_static(filename):
	return static_file(filename, root='static')

@app.route('/')	
@app.route('/remote')
def remote():
	logger.debug('Remote page requested.')
	return template('remote')

@app.route('/stream')	
def stream(): 
	url = request.query['url']	
	logger.debug('Received URL to cast: '+url)

	if 'slow' in request.query:
		if request.query['slow'] in ["True", "true"]:
			config["slow_mode"] = True
		else:
			config["slow_mode"] = False
		with open('raspberrycast.conf', 'w') as f:
			json.dump(config, f)
		
		logger.info("Slow mode changed to: " + config["slow_mode"])
	try:
		if ('localhost' in url) or ('127.0.0.1' in url):
			ip = request.environ['REMOTE_ADDR']
			logger.debug('URL containing localhost adress . Replacing with remote ip :'+ip)
			url = url.replace('localhost', ip).replace('127.0.0.1', ip)

		if 'subtitles' in request.query:
			subtitles = request.query['subtitles']
			logger.debug('Subtitles link is '+subtitles)
			urllib.urlretrieve(subtitles, "subtitle.srt")
			launchvideo(url, True)
		else:
			logger.debug('No subtitles for this stream')
			if ("youtu" in url and "list=" in url) or ("soundcloud" in url and "/sets/" in url):
				playlist(url, True)
			else:
				launchvideo(url, False)
			return "1"
	except Exception, e:
		logger.error('Error in launchvideo function or during downlading the subtitles')
		logger.exception(e)
		return "0"

@app.route('/queue')
def queue():
	url = request.query['url']

	if 'slow' in request.query:
		if request.query['slow'] in ["True", "true"]:
			config["slow_mode"] = True
		else:
			config["slow_mode"] = False
		with open('raspberrycast.conf', 'w') as f:
			json.dump(config, f)
	
	try :
		if getState() != "0" :
			logger.info('Adding URL to queue: '+url)
			if ("youtu" in url and "list=" in url) or ("soundcloud" in url and "/sets/" in url):
				playlist(url, False)
			else:
				queuevideo(url)
			return "2"
		else :
			logger.info('No video currently playing, playing url : '+url)
			if ("youtu" in url and "list=" in url) or ("soundcloud" in url and "/sets/" in url):
				playlist(url, True)
			else:
				launchvideo(url, False)
			return "1"
	except Exception, e:
		logger.error('Error in launchvideo or queuevideo function !')
		logger.exception(e)
		return "0"

@app.route('/video')
def video():
	control = request.query['control']
	if control == "pause" :
		logger.info('Command : pause')
		os.system("echo -n p > /tmp/cmd &")
		return "1"
	elif control in ["stop", "next"] :
		logger.info('Command : stop video')
		os.system("echo -n q > /tmp/cmd &")
		return "1"
	elif control == "right" :
		logger.info('Command : forward')
		os.system("echo -n $'\x1b\x5b\x43' > /tmp/cmd &")
		return "1"
	elif control == "left" :
		logger.info('Command : backward')
		os.system("echo -n $'\x1b\x5b\x44' > /tmp/cmd &")
		return "1"

@app.route('/sound')
def sound():
	vol = request.query['vol']
	if vol == "more" :
		logger.info('REMOTE: Command : Sound ++')
		os.system("echo -n + > /tmp/cmd &")
	elif vol == "less" :
		logger.info('REMOTE: Command : Sound --')
		os.system("echo -n - > /tmp/cmd &")
	setVolume(vol)
	return "1"

@app.route('/shutdown')
def shutdown():
	time = request.query['time']
	if time == "cancel":
		os.system("shutdown -c")
		logger.info("Shutdown canceled.")
		return "1"
	else:	
		try:
			time = int(time)
			if (time<400 and time>=0):
				shutdown_command = "shutdown -h +" + str(time) + " &"
				os.system(shutdown_command)
				logger.info("Shutdown should be successfully programmed")
				return "1"
		except:
			logger.error("Error in shutdown command parameter")
			return "0"
			
@app.route('/running')
def webstate():
	currentState = getState()
	logger.debug("Running state as been asked : "+currentState)
	return currentState
		
run(app, reloader=False, host='192.168.1.27', debug=True, quiet=True, port=2020)
