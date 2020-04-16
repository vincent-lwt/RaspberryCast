#!/usr/bin/env python

import logging
import os
import sys
import json
try:
    # this works in Python3
    from urllib.request import urlretrieve
except ImportError:
    # this works in Python2
    from urllib import urlretrieve
from bottle import Bottle, SimpleTemplate, request, response, \
                   template, run, static_file

from process import launchvideo, queuevideo, playlist, \
                    setState, getState, setVolume, playeraction

from omxplayer.keys import *

if len(sys.argv) > 1:
    config_file = sys.argv[1]
else:
    config_file = 'raspberrycast.conf'
with open(config_file) as f:
      config = json.load(f)

# Setting log
logging.basicConfig(
    filename='RaspberryCast.log',
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt='%m-%d %H:%M:%S',
    level=logging.DEBUG
)
logger = logging.getLogger("RaspberryCast")

# Creating handler to print messages on stdout
root = logging.getLogger()
root.setLevel(logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
root.addHandler(ch)

if config["new_log"]:
    os.system("sudo fbi -T 1 --noverbose -a  images/ready.jpg")

setState("0")
open('video.queue', 'w').close()  # Reset queue
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
        # TODO: Do we really want to write this to disk?
        with open(config_file, 'w') as f:
            json.dump(config, f)

    try:
        if ('localhost' in url) or ('127.0.0.1' in url):
            ip = request.environ['REMOTE_ADDR']
            logger.debug('''URL contains localhost adress. \
Replacing with remote ip : ''' + ip)
            url = url.replace('localhost', ip).replace('127.0.0.1', ip)

        if 'subtitles' in request.query:
            subtitles = request.query['subtitles']

            if ('localhost' in subtitles) or ('127.0.0.1' in subtitles):
                            ip = request.environ['REMOTE_ADDR']
                            logger.debug(
                                '''Subtitle path contains localhost adress.
Replacing with remote IP.''')
                            subtitles = subtitles\
                                .replace('localhost', ip)\
                                .replace('127.0.0.1', ip)

            logger.debug('Subtitles link is '+subtitles)
            urlretrieve(subtitles, "subtitle.srt")
            launchvideo(url, config, sub=True)
        else:
            logger.debug('No subtitles for this stream')
            if (
                    ("youtu" in url and "list=" in url) or
                    ("soundcloud" in url and "/sets/" in url)):
                playlist(url, True, config)
            else:
                launchvideo(url, config, sub=False)
            return "1"
    except Exception as e:
        logger.error(
            'Error in launchvideo function or during downlading the subtitles')
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

    try:
        if getState() != "0":
            logger.info('Adding URL to queue: '+url)
            if (
                    ("youtu" in url and "list=" in url) or
                    ("soundcloud" in url and "/sets/" in url)):
                playlist(url, False, config)
            else:
                queuevideo(url, config)
            return "2"
        else:
            logger.info('No video currently playing, playing url : '+url)
            if (
                    ("youtu" in url and "list=" in url) or
                    ("soundcloud" in url and "/sets/" in url)):
                playlist(url, True, config)
            else:
                launchvideo(url, config, sub=False)
            return "1"
    except Exception as e:
        logger.error('Error in launchvideo or queuevideo function !')
        logger.exception(e)
        return "0"


@app.route('/video')
def video():
    control = request.query['control']
    if control == "pause":
        logger.info('Command : pause')
        playeraction(PAUSE)
        return "1"
    elif control in ["stop", "next"]:
        logger.info('Command : stop video')
        playeraction(EXIT)
        return "1"
    elif control == "right":
        logger.info('Command : forward')
        playeraction(SEEK_FORWARD_SMALL)
        return "1"
    elif control == "left":
        logger.info('Command : backward')
        playeraction(SEEK_BACK_SMALL)
        return "1"
    elif control == "longright":
        logger.info('Command : long forward')
        playeraction(SEEK_FORWARD_LARGE)
        return "1"
    elif control == "longleft":
        logger.info('Command : long backward')
        playeraction(SEEK_BACK_LARGE)
        return "1"


@app.route('/sound')
def sound():
    vol = request.query['vol']
    if vol == "more":
        logger.info('REMOTE: Command : Sound ++')
        playeraction(INCREASE_VOLUME)
    elif vol == "less":
        logger.info('REMOTE: Command : Sound --')
        playeraction(DECREASE_VOLUME)
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
            if (time < 400 and time >= 0):
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

run(app, reloader=False, host='0.0.0.0', debug=True, quiet=True, port=2020)
