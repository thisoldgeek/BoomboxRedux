#!/usr/bin/env python
import sys
import re
#from luma.core.interface.serial import i2c, spi
#from luma.core.render import canvas
#from luma.oled.device import sh1106

artist = ""
track = ""
album = ""
begend = ""

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
#def render(device):
def render():
    #with canvas(device) as draw:
        #draw.text((0, 0), artist, fill="white", align="center")
        #draw.text((0, 20), album, fill="white", align="center")
        #draw.text((0, 40), track, fill="white", align="center")
    print(artist, album, track)

# Create devices
# serial = i2c(port=1, address=0x3C)
#device = sh1106(serial)

# Welcome message
#with canvas(device) as draw:
    #draw.rectangle(device.bounding_box, outline="white", fill="black")
    #draw.text((30, 20), "Ready...", fill="white")

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

