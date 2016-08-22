#!/usr/bin/env python

from __future__ import unicode_literals
from feedgen.feed import FeedGenerator

import ConfigParser
import os
import sys
import json
import youtube_dl
import urllib
import gzip


def api_loop(cache,ytkey,listid):
	url = 'https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&playlistId=%s&key=%s' % (listid , ytkey)
	urlBase = url
	#loop through all of the playlist items from the API
	while True:

		#get the API call
		response = urllib.urlopen(url)

		#read in the API response
		data = json.loads(response.read())

		#loop through the items
		for item in data['items']:
			#check if the item is in the cache
			if item['id'] not in cache.keys():
				#if not, add it
				cache[item['id']] = item
			else:
				#if so, stop processing the API
				return cache

		#API pagenates the results, so process next pages as we get to them
		if 'nextPageToken' in data:
			url = urlBase + '&pageToken=' + data['nextPageToken']
			print data['nextPageToken']
		else:
			break

	return cache


def process_playlist(defaults,playlistConf):

	conf = dict(playlistConf)

	plpath = defaults['outputdir'] + '/' + conf['__name__']

	if not os.path.exists(plpath):
		try:
			os.makedirs(plpath)
		except OSError:
			print "Could not make output directory"
			exit()


	# this is the list of all the times from the playlist.
	# open the cache or create it
	try:
		with gzip.open(plpath + '/.cache.json.gz','rb') as f:
			allitems = json.loads(f.read().decode('ascii'))
	except IOError:
		print 'No file for playlist. Creating new one'
		allitems = dict()



	#do the main loop
	allitems = api_loop(allitems,defaults['ytapi'],conf['listid'])



	fg = FeedGenerator()
	fg.load_extension('podcast')
	fg.podcast.itunes_category(conf['category'],conf['subcategory'])
	fg.title(conf['title'])
	fg.description(conf['description'])
	fg.link(href=defaults['urlbase'], rel='self')


	for key, item in allitems.iteritems():
		s = item['snippet']
		publishedAt =  s['publishedAt']
		title = s['title']
		description = s['description']
		thumbnail =  s['thumbnails']['default']['url']
		vidId = s['resourceId']['videoId']



		fe = fg.add_entry()
		fe.id(vidId)
		fe.title(s['title'])
		fe.description(s['description'])
		fe.enclosure(defaults['urlbase'] + conf['__name__'] + \
			'/' + vidId +'.mp3',0,'audio/mpeg')
		fe.published(s['publishedAt'])

		#skip downloading if we've already downloaded this one
		if 'downloaded' in item and item['downloaded'] is True:
			continue

		ydl_opts = {
			'simulate': False,
			'quiet': True,
			'nooverwrites': True,
			'format': 'bestaudio/best',
			'postprocessors': [{
				'key': 'FFmpegExtractAudio',
				'preferredcodec': 'mp3',
				'preferredquality': '192',
			}],
			'writeinfojson': False,
			'writethumbnail': False,
			'outtmpl': r'{}/%(id)s.%(exts)s'.format(plpath),
		}

		try:
			with youtube_dl.YoutubeDL(ydl_opts) as ydl:
				ydl.download(['https://www.youtube.com/watch?v=%s' % (vidId)])
				allitems[key]['downloaded'] = True;

		except youtube_dl.utils.DownloadError:
			print "[Error] Video id %s \"%s\" does not exist." % (vidId, title)

	#write the cache out
	with gzip.open(plpath + '/.cache.json.gz', 'wb') as f:
	    json.dump(allitems,f)

	fg.rss_str(pretty=True)
	fg.rss_file(plpath + '/feed.xml')

def main():
	if not os.path.isfile('config.ini'):
		print "No config file found. Exiting."
		exit()

	try:
		config = ConfigParser.ConfigParser()
		config.read('config.ini')
	except:
		print "what"
		exit()

	if config.has_section('system'):
		defaults = dict(config._sections['system'])
		print defaults
	else:
		print "No 'System' section found in config file. Exiting."
		exit ()

	if not os.path.exists(defaults['outputdir']):
		try:
			os.makedirs(defaults['outputdir'])
		except OSError:
			print "Could not make output directory"
			exit()

	for section in config.sections():

		if section == 'system':
			continue

		process_playlist(defaults,
				config._sections[section])

if __name__ == "__main__":
	sys.exit(main())








