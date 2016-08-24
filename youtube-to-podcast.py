#!/usr/bin/env python

from __future__ import unicode_literals
from feedgen.feed import FeedGenerator
from mutagen.mp3 import MP3
from mutagen import MutagenError
from collections import OrderedDict

import dateutil.parser
import mutagen.id3
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
		else:
			break

	return cache

def sortByPosition(cache):
	return OrderedDict(
			sorted(
				cache.items(),
				key=lambda x: x[1]['snippet']['position'],
				reverse=True
				)
		)


def seconds_to_hms(seconds):
	m, s = divmod(seconds, 60)
	h, m = divmod(m, 60)
	return "%02d:%02d:%02d" % (h, m, s)


def get_length(mp3file):
	#try and open the file
	try:
		audio = MP3(mp3file)
	except MutagenError:
		pass

	#return length in seconds
	return int(audio.info.length)


def tag_file(tags,mp3file):

	#try and open the file
	try:
		audio = MP3(mp3file)
	except MutagenError:
		pass

	#title
	audio.tags.add(mutagen.id3.TIT2(
		text=tags['vidinfo']['title']))
	#album
	audio.tags.add(mutagen.id3.TALB(
		text=tags['title']))

	#date
	d = dateutil.parser.parse(tags['vidinfo']['publishedAt'])
	audio.tags.add(mutagen.id3.TDRC(
		text=d.strftime('%Y-%m-%d %H:%M:%S')))

	#artist
	audio.tags.add(mutagen.id3.TPE1(
		text=tags['vidinfo']['channelTitle']))

	#genre
	audio.tags.add(mutagen.id3.TCON(
		text=tags['category']))

	#track
	audio.tags.add(mutagen.id3.TRCK(
		text=str(tags['vidinfo']['position'] + 1)))

	#website
	audio.tags.add(mutagen.id3.WOAR(
		url= 'https://youtube.com/watch?v={}'.format(
			tags['vidinfo']['resourceId']['videoId'])
		))

	#length in ms
	audio.tags.add(mutagen.id3.TLEN(
		text=str(int(get_length(mp3file)*1000))
			))

	#add comment
	audio.tags.add(
		mutagen.id3.COMM(
			lang='eng',
			desc='',
			text=tags['vidinfo']['description']
			)
		)

	#podcast flag
	audio.tags.add(mutagen.id3.PCST(value = 1))

	#use vid thumbnail as cover art
	audio.tags.add(
		mutagen.id3.APIC(
			encoding=3, # 3 is for utf-8
			mime='image/jpeg', # image/jpeg or image/png
			type=3, # 3 is for the cover image
			desc=u'Cover',
			data=open(tags['basename']+'.jpg').read()
		)
	)
	audio.save()



def process_playlist(defaults,playlistConf):

	conf = dict(playlistConf)
	tags = conf
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
		print 'No cache file for playlist. Creating new one'
		allitems = dict()



	#do the main loop
	allitems = api_loop(allitems,defaults['ytapi'],conf['listid'])

	#sort the items by playlist position
	allitems = sortByPosition(allitems)

	fg = FeedGenerator()
	fg.load_extension('podcast')
	#fg.load_extension('syndication')
	fg.title(conf['title'])
	fg.description(conf['description'])
	fg.podcast.itunes_summary(conf['description'])
	fg.podcast.itunes_category(conf['category'],conf['subcategory'])
	fg.link(
		href='{}/{}/feed.xml'.format(defaults['urlbase'],conf['__name__']),
		rel='self',
		type='application/rss+xml')
	if 'explicit' in conf:
		ex = conf['explicit']
	else:
		ex = 'no'
	fg.podcast.itunes_explicit(conf['explicit'])
	if 'language' in conf:
		lan = conf['language']
	else:
		lan = 'en-US'
	fg.language(lan)
	#fg.syndication.update_period('hourly')
	#fg.syndication.update_frequency(1)

	for key, item in allitems.iteritems():
		tags['vidinfo'] = item['snippet']

		vidId = tags['vidinfo']['resourceId']['videoId']

		tags['basename'] = '{}/{}'.format(plpath,vidId)


		fe = fg.add_entry()
		fe.id(vidId)
		fe.title(tags['vidinfo']['title'])
		fe.description(tags['vidinfo']['description'])
		fe.enclosure(
			url='{}/{}/{}.mp3'.format(
				defaults['urlbase'] ,
				conf['__name__'],
				vidId),
			length=0,
			type='audio/mpeg')
		fe.published(tags['vidinfo']['publishedAt'])

		if 'duration' in tags['vidinfo']:
			fe.podcast.itunes_duration(seconds_to_hms(tags['vidinfo']['duration']))

		#skip downloading if we've already downloaded this one
		if 'downloaded' in item and item['downloaded'] is True:
			continue

		if 'simulate' in defaults and defaults['simulate'] == 'True':
			simulate = True
		else:
			simulate = False


		ydl_opts = {
			'simulate': simulate,
			'quiet': True,
			'nooverwrites': True,
			'format': 'bestaudio/best',
			'postprocessors': [{
				'key': 'FFmpegExtractAudio',
				'preferredcodec': 'mp3',
				'preferredquality': '192',
			}],
			'writeinfojson': False,
			'writethumbnail': True,
			'outtmpl': r'{}/%(id)s.%(exts)s'.format(plpath),
		}

		try:
			mp3file = '{}/{}.mp3'.format(plpath,vidId)
			with youtube_dl.YoutubeDL(ydl_opts) as ydl:
				ydl.download(['https://www.youtube.com/watch?v=%s' % (vidId)])

			if not simulate:
				allitems[key]['downloaded'] = True;
				tag_file(tags,mp3file)

				if 'duration' not in item['snippet']:
					allitems[key]['snippet']['duration'] = get_length(mp3file)
					fe.podcast.itunes_duration(seconds_to_hms(allitems[key]['snippet']['duration']))


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








