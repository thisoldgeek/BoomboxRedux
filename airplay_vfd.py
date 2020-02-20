#!/usr/bin/env python3

import sys
import re
from time import sleep
import spidev
import VFD

artist = ""
track = ""
album = ""

# initalize SPI
vfd=VFD.SPI()

vfd.init_VFD()

def extract(line):
    m = re.match('^(Title|Artist|Album Name|"ssnc"): \"(.*?)\"\.$', line)
    if m:
        return m.group(1), m.group(2)
    else:
        return None, None

def update(key, val):
    global artist, album, track, begend
    if key == "Artist":
        artist = val
    elif key == "Album Name":
        album = val
    elif key == "Title":
         track = val
    elif key == "ssnc":
         begend = val

def render():
    print(artist, album, track)
    vfd.blank_lines()
    sleep (0.1)
    vfd.setCursor(0,0)
    vfd.text(artist)
    vfd.setCursor(0,1)
    vfd.text(track)

# Main loop
try:
    while True:
        line = sys.stdin.readline()
        key, val = extract(line)
        if key and val:
            update(key, val)
            render()

except KeyboardInterrupt:
    sys.stdout.flush()
    pass

