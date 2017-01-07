import youtube_dl
import os, threading, logging, json

with open('raspberrycast.conf') as f:    
    config = json.load(f)
logger = logging.getLogger("RaspberryCast")

def launchvideo(url, sub=False):
	setState("2")
	
	os.system("echo -n q > /tmp/cmd &") #Kill previous instance of OMX

	if config["new_log"]:
		os.system("sudo fbi -T 1 -a --noverbose images/processing.jpg")

	logger.info('Extracting source video URL...')	
	out = return_full_url(url, sub)

	logger.debug("Full video URL fetched.")
	
	thread = threading.Thread(target=playWithOMX, args=(out, sub,))
	thread.start()
	
	os.system("echo . > /tmp/cmd &") #Start signal for OMXplayer

def queuevideo(url, onlyqueue=False):
	logger.info('Extracting source video URL, before adding to queue...')	

	out = return_full_url(url, False)

	logger.info("Full video URL fetched.")

	if getState() == "0" and onlyqueue == False:
		logger.info('No video currently playing, playing video instead of adding to queue.')
		thread = threading.Thread(target=playWithOMX, args=(out, False,))
		thread.start()
		os.system("echo . > /tmp/cmd &") #Start signal for OMXplayer
	else:
		if out is not None:
			with open('video.queue', 'a') as f:
				f.write(out+'\n')

def return_full_url(url, sub=False):
	logger.debug("Parsing source url for "+url+" with subs :"+str(sub))

	if (url[-4:] in (".avi", ".mkv", ".mp4", ".mp3")) or (sub) or (".googlevideo.com/" in url):	
		logger.debug('Direct video URL, no need to use youtube-dl.')
		return url

	if slow:
		ydl_options = {
			'logger': logger, 
			'noplaylist': True, 
			'ignoreerrors': True,
			'format': 'mp4[height<=480]/best[height<=480]'}
	else:
		ydl_options = {
			'logger': logger, 
			'noplaylist': True, 
			'ignoreerrors': True,
			'format': 'mp4/best'}
	ydl = youtube_dl.YoutubeDL(ydl_options) # Ignore errors in case of error in long playlists
	with ydl: #Downloading youtub-dl infos
	    result = ydl.extract_info(url, download=False) #We just want to extract the info

	if result is None:
		logger.error("Result is none, returning none. Cancelling following function.")
		return None

	if 'entries' in result: #Can be a playlist or a list of videos
	    video = result['entries'][0]
	else:
	    video = result #Just a video

	slow = config["slow_mode"]

	if "youtu" in url:
		if slow:
			for i in video['formats']:
				if i['format_id'] == "18":
					logger.debug("Youtube link detected, extracting url in 360p")
					return i['url']
		else:
			logger.debug('CASTING: Youtube link detected, extracting url in maximal quality.')
			return video['url']
	elif "vimeo" in url:
		if slow:
			for i in video['formats']:
				if i['format_id'] == "http-360p":
					logger.debug("Vimeo link detected, extracting url in 360p")
					return i['url']
		else:
			logger.debug('Vimeo link detected, extracting url in maximal quality.')
			return video['url']
	else :
		logger.debug('Video not from Youtube or Vimeo. Extracting url in maximal quality.')
		return video['url']

def playlist(url, cast_now):
	logger.info("Processing playlist.")

	if cast_now:
		logger.info("Playing first video of playlist")
		launchvideo(url) #Launch first vdeo
	else:
		queuevideo(url)

	thread = threading.Thread(target=playlistToQueue, args=(url,))
	thread.start()
	
def playlistToQueue(url):
	logger.info("Adding every videos from playlist to queue.")
	ydl = youtube_dl.YoutubeDL({'logger': logger, 'extract_flat': 'in_playlist',  'ignoreerrors': True}) 
	with ydl: #Downloading youtub-dl infos
		result = ydl.extract_info(url, download=False)
		for i in result['entries']:
			logger.info("queuing video")
			if i != result['entries'][0]:
				queuevideo(i['url'])

def playWithOMX(url, sub):
	logger.info("Starting OMXPlayer now.")

	setState("1")
	if sub:
		os.system("omxplayer -b -r -o both '" + url + "' --subtitles subtitle.srt < /tmp/cmd")
	elif url is None:
		pass
	else :
		os.system("omxplayer -b -r -o both '" + url + "' < /tmp/cmd")
	
	if getState() != "2": # In case we are again in the launchvideo function
		setState("0")
		with open('video.queue', 'r') as f: #Check if there is videos in queue
			first_line = f.readline().replace('\n', '')
			if first_line != "":
				logger.info("Starting next video in playlist.")
				with open('video.queue', 'r') as fin:
					data = fin.read().splitlines(True)
				with open('video.queue', 'w') as fout:
					fout.writelines(data[1:])
				thread = threading.Thread(target=playWithOMX, args=(first_line, False,))
				thread.start()
				os.system("echo . > /tmp/cmd &") #Start signal for OMXplayer
			else:
				logger.info("Playlist empty, skipping.")
				if config["new_log"]:
					os.system("sudo fbi -T 1 -a --noverbose images/ready.jpg")

def setState(state):
	os.system("echo "+state+" > state.tmp") #Write to file so it can be accessed from everywhere

def getState():
	with open('state.tmp', 'r') as f:
		return f.read().replace('\n', '')
