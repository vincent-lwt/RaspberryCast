import youtube_dl
import os
import threading
import logging
import json
import requests
import hot
logger = logging.getLogger("RaspberryCast")
volume = 0


def launchvideo(url, config, sub=False):
    setState("2")

    os.system("echo -n q > /tmp/cmd &")  # Kill previous instance of OMX

    if config["new_log"]:
        os.system("sudo fbi -T 1 -a --noverbose images/processing.jpg")

    logger.info('Extracting source video URL...')
    out = return_full_url(url, sub=sub, slow_mode=config["slow_mode"])

    logger.debug("Full video URL fetched.")

    thread = threading.Thread(target=playWithOMX, args=(out, sub,),
            kwargs=dict(width=config["width"], height=config["height"],
                        new_log=config["new_log"]))
    thread.start()

    os.system("echo . > /tmp/cmd &")  # Start signal for OMXplayer


def queuevideo(url, config, onlyqueue=False):
    logger.info('Extracting source video URL, before adding to queue...')

    out = return_full_url(url, sub=False, slow_mode=config["slow_mode"])

    logger.info("Full video URL fetched.")

    if getState() == "0" and not onlyqueue:
        logger.info('No video currently playing, playing video instead of \
adding to queue.')
        thread = threading.Thread(target=playWithOMX, args=(out, False,),
            kwargs=dict(width=config["width"], height=config["height"],
                        new_log=config["new_log"]))
        thread.start()
        os.system("echo . > /tmp/cmd &")  # Start signal for OMXplayer
    else:
        if out is not None:
            with open('video.queue', 'a') as f:
                f.write(out+'\n')


def return_full_url(url, sub=False, slow_mode=False):
    logger.debug("Parsing source url for "+url+" with subs :"+str(sub))

    if ((url[-4:] in (".avi", ".mkv", ".mp4", ".mp3")) or
            (sub) or (".googlevideo.com/" in url)):
        logger.debug('Direct video URL, no need to use youtube-dl.')
        return url

    ydl = youtube_dl.YoutubeDL(
        {
            'logger': logger,
            'noplaylist': True,
            'ignoreerrors': True,
        })  # Ignore errors in case of error in long playlists
    with ydl:  # Downloading youtub-dl infos. We just want to extract the info
        result = ydl.extract_info(url, download=False)

    if result is None:
        logger.error(
            "Result is none, returning none. Cancelling following function.")
        return None

    if 'entries' in result:  # Can be a playlist or a list of videos
        video = result['entries'][0]
    else:
        video = result  # Just a video

    if "youtu" in url:
        if slow_mode:
            for i in video['formats']:
                if i['format_id'] == "18":
                    logger.debug(
                        "Youtube link detected, extracting url in 360p")
                    return i['url']
        else:
            logger.debug('''CASTING: Youtube link detected.
Extracting url in maximal quality.''')
            for fid in ('22', '18', '36', '17'):
                for i in video['formats']:
                    if i['format_id'] == fid:
                        logger.debug(
                            'CASTING: Playing highest video quality ' +
                            i['format_note'] + '(' + fid + ').'
                        )
                        return i['url']

    if "hots" in url:
        hotsapi = "https://api.hotstar.com/h/v1/play?contentId="

        id = url[len(url) - 16: len(url) - 6]
        #Hack to check if a valid id
        try:
            temp = int(id)
        except ValueError:
            id = url[len(url) - 10: len(url)]

        hotsapi += id
        headers = {'Hotstarauth': hot.generateAuth(), 'X-Country-Code':'IN', 'X-Platform-Code': 'JIO'}

        resp = requests.get(hotsapi, headers=headers)
        jsonresp = json.loads(resp.text)
        pburl = jsonresp['body']['results']['item']['playbackUrl']

        return pburl

    elif "vimeo" in url:
        if slow_mode:
            for i in video['formats']:
                if i['format_id'] == "http-360p":
                    logger.debug("Vimeo link detected, extracting url in 360p")
                    return i['url']
        else:
            logger.debug(
                'Vimeo link detected, extracting url in maximal quality.')
            return video['url']
    else:
        logger.debug('''Video not from Youtube or Vimeo.
Extracting url in maximal quality.''')
        return video['url']


def playlist(url, cast_now, config):
    logger.info("Processing playlist.")

    if cast_now:
        logger.info("Playing first video of playlist")
        launchvideo(url, config)  # Launch first video
    else:
        queuevideo(url, config)

    thread = threading.Thread(target=playlistToQueue, args=(url, config))
    thread.start()


def playlistToQueue(url, config):
    logger.info("Adding every videos from playlist to queue.")
    ydl = youtube_dl.YoutubeDL(
        {
            'logger': logger,
            'extract_flat': 'in_playlist',
            'ignoreerrors': True,
        })
    with ydl:  # Downloading youtub-dl infos
        result = ydl.extract_info(url, download=False)
        for i in result['entries']:
            logger.info("queuing video")
            if i != result['entries'][0]:
                queuevideo(i['url'], config)


def playWithOMX(url, sub, width="", height="", new_log=False):
    logger.info("Starting OMXPlayer now.")

    logger.info("Attempting to read resolution from configuration file.")

    resolution = ""

    if width or height:
        resolution = " --win '0 0 {0} {1}'".format(width, height)

    setState("1")
    if sub:
        os.system(
            "omxplayer -b -r -o both '" + url + "'" + resolution +
            " --vol " + str(volume) +
            " --subtitles subtitle.srt < /tmp/cmd"
        )
    elif url is None:
        pass
    else:
        os.system(
            "omxplayer -b -r -o both '" + url + "' " + resolution + " --vol " +
            str(volume) + " < /tmp/cmd"
        )

    if getState() != "2":  # In case we are again in the launchvideo function
        setState("0")
        with open('video.queue', 'r') as f:
            # Check if there is videos in queue
            first_line = f.readline().replace('\n', '')
            if first_line != "":
                logger.info("Starting next video in playlist.")
                with open('video.queue', 'r') as fin:
                    data = fin.read().splitlines(True)
                with open('video.queue', 'w') as fout:
                    fout.writelines(data[1:])
                thread = threading.Thread(
                    target=playWithOMX, args=(first_line, False,),
                        kwargs=dict(width=width, height=height,
                                    new_log=new_log),
                )
                thread.start()
                os.system("echo . > /tmp/cmd &")  # Start signal for OMXplayer
            else:
                logger.info("Playlist empty, skipping.")
                if new_log:
                    os.system("sudo fbi -T 1 -a --noverbose images/ready.jpg")


def setState(state):
    # Write to file so it can be accessed from everywhere
    os.system("echo "+state+" > state.tmp")


def getState():
    with open('state.tmp', 'r') as f:
        return f.read().replace('\n', '')


def setVolume(vol):
    global volume
    if vol == "more":
        volume += 300
    if vol == "less":
        volume -= 300
