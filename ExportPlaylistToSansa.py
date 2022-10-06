import os
import sys
import shutil
import codecs
import eyed3
import unicodedata
from xml.sax.saxutils import unescape

####################################################################################################
# README:                                                                                          #
# =======                                                                                          #
# This scripts was written for home use by any sansa clip user                                     #
# that aims to sync their windows media player playlists to the                                    #
# player they own.                                                                                 #
#                                                                                                  #
# The scripts will do the following:                                                               #
# 1) Find and Copy the playlists songs to the player                                               #
# 2) Configure a .m3u playlist on the sansa player (supported by the player)                       #
# 3) Supports .mp3 songs that include Unicode paths (not originally supported by the .m3u format)  #
#                                                                                                  #
# Playlist notes:                                                                                  #
# .m3u playlists are partially supported by the sansa player, and the songs are                    #
# shown according to their PATH NAMES, and NOT their "title" (like shown in the song list).        #
# The script will bypass this behavior in the following way:                                       #
# 1) .mp3 songs will be copied using the "title", as shown in the mp3 tags                         #
# 2) In case the "title" includes Unicode chars:                                                   #
# 2.1) In case the "comment" tag is present, it will be used as the actual name                    #
# 2.2) Otherwise, the user will be prompted to enter a name (ascii only).                          #
#      This name will be prefixed using '_' and stored in the "comment" tag for later use          #
#                                                                                                  #
# The script is configurable, and any user that want to save it's Unicode replacement              #
# names with another prefix, or another tag, can freely do it.                                     #
####################################################################################################

###################
# dynamic configs #
###################

# running flags
flag_should_remove_unused_songs = False # Default value. Recommended value is "True"
flag_dry_run 					= True  # Default value. Recommended value is "False"

# sansa player constants
sansa_dir			= "ENTER THE DRIVE LETTER OF THE SANSA PLAYER"  # Configure this field.
																	# For example: "E:\\"

# wanted playlists
playlist_base_path	= "ENTER AN ABSOLUTE PATH TO YOUR MEDIA PLAYER PLAYLIST DIRECTORY"  # Configure this field.
																						# For Example: "C:\\Users\\user\\Music\\Playlists"
playlist_names		= [] # Configure this field.
						 # Should include a list of playlist file names (.wpl files) from the above directory.
my_playlists 		= map(lambda x : playlist_base_path + x, playlist_names)

#####################################################################################
# NOTE: additional absolute paths can be added manually to the "my_playlists" list. #
# This list will be used by the rest of the script.                                 #
#####################################################################################

# unicode configurations
unicode_prefix = '_'

##################
# static configs #
##################

# .wpl constants
song_prefix = '<media src="'

# sansa player constants
music_folder 	= sansa_dir + "Music\\"
playlist_folder = sansa_dir + "Playlists\\"


# Global variables
seenSongs = {}

##
# Exports the songs list to a newly created playlist
##
def createPlaylist(playlist, songs) :
	playlist_name = getPlaylistName(playlist)
	playlist = open(playlist_folder + playlist_name + '.m3u', 'w')
	# add the header
	# IMPORTANT: The 1st line must be a comment, because it will always be skipped by SanDisk's firmware
	playlist.write('# A comment to be skipped by SanDisk\'s firmware\n')
	for song in songs :
		playlist.write(".." + os.path.sep + music_folder.replace(sansa_dir, "") + song[1].split(os.path.sep)[-1] + '\n')
		
	# close the file
	playlist.close()

##
# Exports the songs list to the newly created directory
##
def exportSongs(path, songs) :
	for song in songs :
		shutil.copy(song, os.path.join(path, song.split(os.path.sep)[-1]))
		
##
# Reads the song list from the sansa player
##
def getPlayerSongs() :
	songs = []
	
	# list all songs in the music base path
	for file in os.listdir(music_folder) :
		suffix = file.split('.')[-1].lower()
		if suffix in ['mp3', 'wmv', 'mp4', 'm4a'] :
			songs.append(music_folder + file)
	
	return songs
	
##
# Checks if the given string contains only ascii chars
##
def is_ascii(s):
    return all(ord(c) < 128 for c in s)
	
##
# Updates the filename so it won't include unicode chars
##
def updateFileName(abspath, name) :
	# should check for .mp3 
	suffix 			= abspath.split('.')[-1]
	can_convert		= suffix.lower() == 'mp3'
	# check the name for unicode chars
	need_convert	= not is_ascii(name)
	manual_help		= False
	
	# decide what to do
	# need to convert and can't do it :(
	if need_convert and not can_convert :
		manual_help = True
		
	# can't convert, but the name is ascii
	elif not can_convert :
		return name
		
	# can convert, and name is ascii
	elif not need_convert :
		tag = lambda x : x.tag.title
		
	# can convert, and needs to do it
	else :
		tag = lambda x : x.tag.comments.get(u"",)._text
		
	# read the comment and adjust the name
	song = eyed3.load(abspath)
	if song is None :
		tag = lambda x : name

	if not manual_help :
		try :
			new_name = unicodedata.normalize('NFKD', tag(song)).encode('ascii','ignore')
			# catch the empty names
			if len(new_name) <= 1 :
				raise ValueError('Unicode named song, without a known translation for it...')
		except Exception, e :
			manual_help = True
	
	# manual intervention
	if manual_help :
		print 'Song %s needs a name.' % (repr(abspath))
		input = raw_input("Enter the wanted name: ")
		try :
			if can_convert :
				song.tag._comments.set(unicode(input))
				song.tag.save(encoding="utf8")
		except IOError, error :
			# permission denied
			pass
		# return None
		new_name = input
		
	# trim irrelevant '_' markers
	while new_name.startswith(unicode_prefix) :
		new_name = new_name[1:]
		
	# add the prefix for it (if needed)
	return (unicode_prefix if need_convert else '') + new_name + '.' + suffix
	
##
# Extracts the songs' paths from the playlist path
##
def getPlaylistSongs(playlist) :
	global seenSongs
	
	songs = []
	
	play_path = os.path.abspath(playlist)
	play_path = os.path.sep.join(play_path.split(os.path.sep)[:-1])
	
	# traverse the lines
	for line in codecs.open(playlist, encoding='utf-8').readlines() :
		trimmed = line.strip()
		if trimmed.startswith(song_prefix) :
			trimmed = trimmed[len(song_prefix) : ]
			part_path = unescape(trimmed[ : trimmed.find('"')].encode('utf-8'), {"&apos;": "'", "&quot;": '"'}).decode('utf-8')
			abs_path  = os.path.abspath(os.path.join(play_path, part_path))
			file_name = part_path.split(os.path.sep)[-1]
			if abs_path not in seenSongs :
				seenSongs[abs_path] = updateFileName(abs_path, file_name)
			file_name = seenSongs[abs_path]
			if file_name is None :
				continue
			songs.append((abs_path, music_folder + file_name))
	
	# return the songs' paths
	return songs

##
# Extracts the playlist's name from it's full path
##
def getPlaylistName(filename) :
	return filename.split(os.path.sep)[-1].split('.')[0]

##
# Prints Usage instructions
##
def printUsage(args) :
	print 'Usage: %s' % (args[0].split(os.path.sep)[-1])
	print 'Exiting'
	exit(1)

##
# Main function
##
def main(args) :
	# check the args
	if len(args) != 1 + 0:
		print 'Wrong amount of arguments, expected 0.'
		printUsage(args)
		
	# silence the library
	eyed3.log.setLevel("ERROR")
	
	# look for a dry run
	if flag_dry_run :
		print 'NOTICE: running in "dry run" mode, no actions will be performed on the player'
	
	# 1st Get a list of the songs on the player
	song_list = getPlayerSongs()
	print 'Read the song list from the player - %d songs' % (len(song_list))
	
	# 2nd For each playlist get it's song list
	play_songs	= {}
	pc_songs 	= set([])
	for playlist in my_playlists :
		# return a list of tuple: (PC path, Player path)
		play_songs[playlist] = getPlaylistSongs(playlist)
		print 'Parsed the playlist %s - %d songs' % (getPlaylistName(playlist), len(play_songs[playlist]))
		
		# 3rd Write the playlist files to the player
		if not flag_dry_run :
			createPlaylist(playlist, play_songs[playlist])
			print 'Created the matching playlist on the sansa player'
		
		# update the pc song set
		for pc, song in play_songs[playlist] :
			pc_songs.add(song)
		
	# 4th build the add_list and remove_list for the sansa player
	add_list 	= set(pc_songs).difference(song_list)
	remove_list = set(song_list).difference(pc_songs)
	
	# 5th Update the actual songs, according to the lists

	##########
	# remove #
	##########
	
	# dry run
	if flag_dry_run :
		print 'Can remove unwanted songs - %d songs' % (len(remove_list))
	# actual removal (if configured)
	elif flag_should_remove_unused_songs :
		print 'Removing the unwanted songs - %d songs' % (len(remove_list))
		for song in remove_list :
			os.remove(song)

	#######
	# add #
	#######
	
	# dry run
	if flag_dry_run :
		print 'New songs can be added - %d songs' % (len(add_list))
	# actual addition
	else :
		print 'Adding the new songs - %d songs' % (len(add_list))
		for playlist in my_playlists : 
			for pc, song in play_songs[playlist] :
				if song in add_list :
					# add the song and update the add list
					try :
						shutil.copy(pc, song)
					except Exception, e:
						print 'Failed to transfer song:', song
						print e
					add_list.remove(song)
	
	# finished
	print 'Finished successfully'

# actually start
if __name__ == "__main__":
	main(sys.argv)