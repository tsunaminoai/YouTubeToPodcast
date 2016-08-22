# Youtube to Podcast #

This project is a tool to pull down YouTube playlists and present them as podcasts.

### Why? ###

There are many YouTube channels that are great for folks who want to discuss things at length. However, generally speaking, most of these interesting talks are not very visually stimulating and shouldn't require us to be in front of a computer or have an app running in the foreground. Many of these creators don't have the means or desire to mirror their content in a podcast format, so this tool does it for them (or you).

### How do I get set up? ###

####Requirements####
Install the python requirements by running:

```
pip install -r requirements.txt
```

The tool also requires either ffmpeg or avconv to be installed on the system

####Setup####

You will need to acquire a YouTube API key from [Google](https://developers.google.com/youtube/v3/)

After you have your key, copy config.ini.dist to config.ini and edit as necessary. It is not advisable to have the tool in the same folder as the output directory.

The tool can me configured with multiple playlists to monitor. Just add additional playlist blocks to the config.

You may want to run the tool on a cron to download the latest additions to the configured playlists.

####Output####

The tool downloads the playlist via the API and then runs through each video. If it has not done so previously, it will download the video and convert to mp3. A feed.xml file is placed into the playlist output directory.

To add the podcast to your device, simply subscribe to a url defined as 
```
http://<baseurl>/<playlist block name>/feed.xml
```