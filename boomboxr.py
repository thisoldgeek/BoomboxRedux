#!/usr/bin/env python3
#
# boomboxr.py - Short for Boombox Redux, an updated DIY boombox; original was 2014
# An mpd player front end for the raspberry pi
#  "Improvements" to other contributors by bob murphy
#   thisoldgeek.blogspot.com
#
# Acknowledgements:
#   VFD code -  original for LCD by ladyada (Limor Fried), et alia
#               translated to python idiom by thisoldgeek  
#   rotary encoder - Bob Rathbone
#   basic lirc remote tutorial - Dr. Simon Monk/Adafruit, et alia - 
#
#  Cited below, the original source of code was lost.
#  If you recognize your code, let me know so I can 
#  acknowledge your efforts.
#  
#  MPD Client Polling - possible source:http://www.tefnet.pl/home_automation/lirc-mpd
#
#  And many others on the interwebz!
#
#
# Changes from rpi_boombox v2 http://github.com/thisoldgeek as of February 17, 2020
#       weather feed change to DarkSky
#       feedparser removed and forecastio added for DarkSky
#       using patched pyrlirc from https://github.com/project-owner/Peppy.doc/wiki/Pylirc
#       using python-mpd2 from https://github.com/Mic92/python-mpd2 
#       added bounds check and VFD message for "End of Playlist" to avoid error when doing "next"
#       updated URLs in classical.m3u playlist to newer, working (ATM) streams
#       changed wording on VFD shutdown message to indicate safe "off" for modern Pi's
#       changed hardware pin assignments for rotary encoder due to use conflict
#       changed to latest Bob Rathbone rotary encoder class circa 2017 from https://github.com/bobrathbone/piradio/blob/master/rotary_class.py
#       fixed error for: DeprecationWarning: time.clock has been deprecated in Python 3.3 and will be removed from Python 3.8: 
#                        use time.perf_counter or time.process_time instead. Solution: just change to time.time from time.clock! Ha, ha!
#       Airplay code based on App Code Labs post: https://appcodelabs.com/show-artist-song-metadata-using-airplay-on-raspberry-pi
#       
import logging
import pylirc as lirc  # this line was updated
import mpd
import os
import sys
import time
import re

import forecastio

from time import sleep
import spidev
import VFD

import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
music_display= 0          # toggle this variable to tell arduino to show light effects for music
                          # you can't read an output directly, so read the variable and set the output
GPIO.setup(24, GPIO.OUT, initial=GPIO.LOW)

from mpd import MPDClient, MPDError, CommandError

from rotary_class import RotaryEncoder


#logging.basicConfig(filename='vfd.log',level=logging.INFO)

keep_running = 1

vol_knob_chg = None

play_toggle = 1

starttime=time.time() - 10 # used to refresh display, set 10 sec IN THE PAST to force display on startup

state = 'play'   # play/pause; when paused, clears screen and does not refresh, allowing airplay metadata to display from separate program


# API Weather Variables - change for your Key and location
api_key = "2878ea4f28cdcfb2e5bfd4bf5ec46ed0" # Dark Sky API Key - Go to https://darksky.net/dev/ and sign up for a free API key
# Use http://www.latlong.net to get the following lat/lng values (required for API)
lat = 37.961461
lng = -122.087975
MyLocation = "Pleasant Hill" # A place name for your weather location

forecast = forecastio.load_forecast(api_key, lat, lng)

weather_check_time = 900 # Check the feed every 15 minutes; Dark Sky API allows 1000 calls per day on free account
weather_start_time = time.time() - weather_check_time	# forces a weather api call on start-up 

global time24
time24 = False	# If True, uses 24 hour clock, else 12 hour clock

centigrade = False  # centigrade = True, use degrees C; False, use degrees Fahrenheit
curr_cond = "clear"

# General Menu processing class
class Menu():
    def __init__(self):
        self.load_playlist = 0

        self.current_col = 0
        self.current_row = 0

        # current_display: m=mpd, t=time, w=weather
        self.running_pgm = "m"

        # dictionary of menu choices, by level of how deep into the menu
        self.menutext = {"1.":"mpd time weather"}   

        self.lvl = "1."  # menu level 
        # four choices at cursor column 0, 4 and 9
        self.lvl1_cursors={0:1, 4:2, 9:3}

        self.current_cursors = self.lvl1_cursors
        self.this_cursor = self.current_cursors[self.current_col]
        self.vol = 0

    def show_menu(self):
        #print ("in show_menu")
        thistext=self.menutext[self.lvl]
        vfd.blank_lines()
        vfd.setCursor(0,0)
        vfd.text(thistext)
        vfd.setCursor(0,0)
        vfd.blink_on()
        self.current_col=0
        self.current_row=0
        if self.lvl == "1.":
           self.current_cursors=self.lvl1_cursors
        elif self.lvl == "1.1":
             self.current_cursors=self.lvl1_1_cursors

    def nav(self, direction):
        #get the current level cursor assignments for menu choices
        self.this_cursor = self.current_cursors[self.current_col] 
        
        if direction == "R":  
           self.this_cursor = self.this_cursor + 1
        elif direction == "L":
           self.this_cursor = self.this_cursor - 1  
        if self.this_cursor < 1:
           self.this_cursor = 1
        if self.this_cursor > len(self.current_cursors):
           self.this_cursor = len(self.current_cursors)
        
        for col, nbr in list(self.current_cursors.items()):
            if nbr == self.this_cursor:
               self.current_col = col
        vfd.setCursor(self.current_col,0) 

class PollerError(Exception):
    """Fatal error in poller."""

class MPDPoller(object):
    def __init__(self, host="localhost", port="6600", password=None):
        self._host = host
        self._port = port
        self._password = password
        self._client = MPDClient()
        self.song = "song"

    def connect(self):
        try:
            self._client.connect(self._host, self._port)

        # Catch socket errors
        except IOError as err:                           # line changed for python3
            print("I/O error: {0}".format(err))          # line changed for python3
            raise PollerError("Could not connect to '%s': %s" %(self._host, err))   # line changed for python3

        # Catch all other possible errors
        # ConnectionError and ProtocolError are always fatal.  Others may not
        # be, but we don't know how to handle them here, so treat them as if
        # they are instead of ignoring them.
        except MPDError as e:
            raise PollerError("Could not connect to '%s': %s" %
                              (self._host, e))

        if self._password:
            try:
                self._client.password(self._password)

            # Catch errors with the password command (e.g., wrong password)
            except CommandError as e:
                raise PollerError("Could not connect to '%s': "
                                  "password commmand failed: %s" %
                                  (self._host, e))

            # Catch all other possible errors
            except (MPDError, IOError) as e:
                raise PollerError("Could not connect to '%s': "
                                  "error with password command: %s" %
                                  (self._host, e))

    def disconnect(self):
        # Try to tell MPD we're closing the connection first
        try:
            self._client.close()

        # If that fails, don't worry, just ignore it and disconnect
        except (MPDError, IOError):
            pass

        try:
            self._client.disconnect()

        # Disconnecting failed, so use a new client object instead
        # This should never happen.  If it does, something is seriously broken,
        # and the client object shouldn't be trusted to be re-used.
        except (MPDError, IOError):
            self._client = MPDClient()

    def poll(self):
        try:
            self.song = self._client.currentsong()

        # Couldn't get the current song, so try reconnecting and retrying
        except (MPDError, IOError):
            # No error handling required here
            # Our disconnect function catches all exceptions, and therefore
            # should never raise any.
            self.disconnect()

            try:
                self.connect()

            # Reconnecting failed
            except PollerError as e:
                raise PollerError("Reconnecting failed: %s" % e)

            try:
                self.song = self._client.currentsong()

            # Failed again, just give up
            except (MPDError, IOError) as e:
                raise PollerError("Couldn't retrieve current song: %s" % e)

        # Hurray!  We got the current song without any errors!
        #print self.song
        




#blocking = 0;   #set to 1 for blocking = on
conf = "/home/pi/scripts/lirc.config"

#pylirc.init("pylirc", conf, blocking)



# initialize mpc client
mpc = mpd.MPDClient()

# initalize SPI
vfd=VFD.SPI()

vfd.init_VFD()

#initialize Menu processing
menu=Menu()
#menu.init_Menu()

#initialize Poller
poller = MPDPoller()
poller.connect()

def mpd_info():
        global state # pause/play

        menu.running_pgm = "m"
	#song=mpc.currentsong()
        poller.poll()
        song = poller.song
	#print song
        #status=mpc.status()
        #vol=status['']
        #print vol
 # Display the song title and author on the VFD

        if state == "pause":  # used so AirPlay can display to VFD
           return

        vfd.blank_lines()
        sleep (0.1)

        if 'title' in song:
            SongTitle = song['title']
        elif 'file' in song:
            SongTitle = song['file']
        else:
            SongTitle = 'Song Title Unknown'

        if 'name' in song:
            Station = song['name']
        else:
            Station = 'Station Unknown'

        a = re.split(": | - ",SongTitle)
     
        #print(a[0])
        vfd.setCursor(0,0)
        vfd.text(a[0])
        
        if len(a)>1:
           #print(a[1])
           vfd.setCursor(0,1)
           # Send SongTitle to VFD
           vfd.text(a[1])

def pgm_info(msg):
        vfd.blank_lines()
        sleep (0.1)
        vfd.setCursor(0,0)
        vfd.text(msg)

def airplay_info():  # requires cat of /tmp/shairplay sync metadata running
        global artist, album, track
        menu.running_pgm = "a"
        mpc.pause()
        line = sys.stdin.readline()
        sleep(0.2)
        m = re.match('^(Title|Artist|Album Name): \"(.*?)\"\.$', line)
        if m:
            key = m.group(1) 
            val = m.group(2)
        else:
            key = None
            val = None

        if key == "Artist":
            artist = val
        elif key == "Album Name":
            album = val
        elif key == "Title":
            track = val

        airplay_vfd()

def airplay_vfd():
    print(artist, album, track)
    vfd.blank_lines()
    sleep (0.1)
    vfd.setCursor(0,0)
    vfd.text(artist)
    vfd.setCursor(0,1)
    vfd.text(track)


# Toggle LED Matrix and NeoPixels on and off based on 'back' button 
def lights_to_music():  
        global music_display
        if music_display:  # if music effects are on, turn them off
           GPIO.output(24, False)
           music_display = False
           #print "turning LEDs off"
        else: 
           GPIO.output(24, True)        # if music effects are OFF, turn them on
           music_display = True
           #print "turning LEDs ON!"
        



def mpd_playlist(pl):
    mpc.clear()
    mpc.load(pl)
    mpc.play(0)
    mpd_info()

def select_menu():
    #print ("this_cursor")
    #print (menu.this_cursor)
    next_lvl=menu.lvl+str(menu.this_cursor)
    ret_val = menu.menutext.get(next_lvl, None)
    
    if ret_val == None:
        this_rtn = run_rtn.get(next_lvl, None)
    
    # need to call the routine by reference
        menu.lvl = "1."
        menu.this_cursor = menu.current_cursors[0]
        vfd.blink_off()
        this_rtn()
    else:
       # descend into the menu tree
       menu.lvl = next_lvl
       #print ("next lvl")
       #print menu.lvl
       
       menu.show_menu()

def play_pause():
    global play_toggle
    if play_toggle:
       play_toggle = 0
    else:
       play_toggle = 1
    mpc.pause(play_toggle) 
 
def prev():
    mpc.previous()
    mpd_info()  

def next():
    pl=mpc.status()
    curr_song_num = pl['song']
    pl_length = pl['playlistlength']
    if (int(curr_song_num) +1) == int(pl_length):
        pgm_info("End of Playlist")   
    else:
        mpc.next()
        mpd_info()

def incr_vol():
    status=mpc.status()
    vol=status['volume']
    if int(vol) >= 95:
        vol=95
    vfd.volume(int(vol),5)
    mpc.setvol(int(vol)+5)

def decr_vol():
    status=mpc.status()
    vol=status['volume']
    if int(vol) <= 5:
        vol = 5
    vfd.volume(int(vol),-5)
    mpc.setvol(int(vol)-5)

def time_info():
    #print ("in time info")
    vfd.blank_lines()
    vfd.setCursor(0,0)
    vfd.text(time.strftime(" %B %d %I:%M %p", time.localtime()))
    menu.running_pgm = "t"

def weather_info():
    global weather_start_time
    global weather_check_time
    global api_key
    global lat
    global lng
    global conds
    global temp_f
    global temp_c
    global time24
    global humidityStr
    global windStr

    if time.time() - weather_start_time > weather_check_time:	# check the number of seconds in weather_check_time has passed
        weather_start_time = time.time()
        forecast = forecastio.load_forecast(api_key, lat, lng)
        current = forecast.currently()
        conds = current.summary
        temp_f = round(current.temperature)
        humidity = current.humidity
        humidity = humidity * 100 # get percent
        humidityStr = str(int(humidity))
        wind = current.windSpeed
        windStr = str(int(wind))
    
    if time24 is True:		
        myTime = time.strftime("%H:%M")
    else:
        myTime = time.strftime("%-I:%M%p")

    if centigrade:	
        timetempStr = myTime +" "+ str(temp_c) + "C"	# centigrade = True
    elif centigrade is False: 
        timetempStr = myTime +" "+ str(temp_f)	+ "F"

    to_VFD = conds
    #print to_VFD
    vfd.blank_lines()
    vfd.setCursor(0,0)
    vfd.text(timetempStr+" "+humidityStr+"%"+" "+windStr+"MPH")
    vfd.setCursor(0,1)
    vfd.text(to_VFD)
    
    # set weather to show on the display
    menu.running_pgm = "w"
  

def current_display():
    #tstamp = time.strftime("%Y/%m/%d %H:%M:%S", time.localtime())
    #logging.info(tstamp)
    
    #print menu.running_pgm
    
    if menu.running_pgm == "m":      # we are displaying mpd info now
       mpd_info()

    if menu.running_pgm == "t":      #get the time and display it
       time_info()

    if menu.running_pgm == "w":      # now we are showing the weather
       weather_info()

    if menu.running_pgm == "a":      # now we are showing AirPlay data
       airplay_info()

def quit():
    vfd.blank_lines()
    vfd.setCursor(0,0)
    vfd.text("<= Shutting Down! =>")
    vfd.setCursor(0,1)
    vfd.text("Green LED out = OFF")
    mpc.setvol(5)
    global keep_running
    keep_running=0


# Define GPIO inputs
VOLUME_UP =     17 	# Pin 11   Clockwise
VOLUME_DOWN =   27	# Pin 13   Anticlockwise
MUTE_SWITCH =   22	# Pin 15    Button Down

# This is the event callback routine to handle events
def volume_event(event):
        global vol_knob_chg
        if event == RotaryEncoder.CLOCKWISE:
		# "Clockwise" is volume up
                # "fake" a remote control key press for vol up
                vol_knob_chg = [{'repeat': 0, 'config': 'volup'}]
                #vol_knob_chg = 'volup'
        elif event == RotaryEncoder.ANTICLOCKWISE:
		# "Anticlockwise" is volume down
                # "fake" a key press
                vol_knob_chg = [{'repeat': 0, 'config': 'voldown'}]
                #vol_knob_chg = 'voldown'
        elif event == RotaryEncoder.BUTTONDOWN:
                print("Button down")
        elif event == RotaryEncoder.BUTTONUP:
                print("Button up")
        return
    

volumeknob = RotaryEncoder(VOLUME_UP,VOLUME_DOWN,MUTE_SWITCH,volume_event,2)  # "2" is board 'revision', latest boards as of 2017 code

commands={
	"playpause":	lambda: play_pause(),
	"prev":		lambda: prev(),
	"next":		lambda: next(),
	"random":	lambda: random(),
	"quit":		lambda: quit(),
	"voldown":	lambda: decr_vol(),
	"volup":	lambda: incr_vol(),
        "left":         lambda: menu.nav("L"),
        "right":        lambda: menu.nav("R"),
        "enter":        lambda: select_menu(),
	"bright":	lambda: vfd.brightnessAdjust(),
	"playlist1":	lambda: mpd_playlist("webstream"),
	"playlist2":	lambda: mpd_playlist("classical_sd"),
	"playlist3":	lambda: mpd_playlist("newage"),
	"playlist4":	lambda: mpd_playlist("rock"),
	"5":		lambda: search(5),
	"6":		lambda: search(6),
	"7":		lambda: search(7),
	"8":		lambda: search(8),
	"9":		lambda: search(9),
        "back":         lambda: lights_to_music(),
        "setup":        lambda: menu.show_menu()
}


# dictionary of methods to run when menu choice is made                
run_rtn = {"1.1":mpd_info,
           "1.2":time_info,
           "1.3":weather_info,
           "1.4":airplay_info
          }

#print("<==== Mainline Starts ====>")
lirc.init("radio")

while keep_running:  
        sleep(.25)      # keep the loop from eating up CPU time!
        
        if  (time.time() - starttime) >= 5:        # refresh the screen every 5 seconds
            starttime=time.time()
            current_display()  
    
        presses = lirc.nextcode(1)
        #if presses != None:
        #   print("lirc.nextcode:",presses)

        # get state - airplay will only display metadata on mpc pause
        #mpc.connect("localhost", 6600)
        #status = mpc.status()
        #mpc.disconnect()
        #print(status['state'])

        if vol_knob_chg != None:
           presses = vol_knob_chg

        if presses == None:
           continue   

        for press in presses:
                try:
                       cmd=commands[press["config"]]
                except KeyError:
                        print("getting KeyError")
                        continue
                try:
                        mpc.connect("localhost", 6600)
                        cmd()
                        status = mpc.status()
                        state = status['state']
                        mpc.disconnect()
                except mpd.ConnectionError:
                        pass

        vol_knob_chg = None

#pylirc.exit()
os.system("sudo shutdown -h now")


