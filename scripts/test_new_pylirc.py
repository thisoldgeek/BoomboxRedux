import pylirc as lirc
import time

blocking = 0
conf = "/home/pi/scripts/lirc.config"
# pylirc.init("pylirc", conf) 

#commands={"volup":  lambda: incr_vol(), "voldown":  lambda: decr_vol() }

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

def incr_vol():
    print("increment volume")

def decr_vol():
    print("decrement volume")

lirc.init("radio")

while True:
    presses=lirc.nextcode(1)
    print(presses)
    if presses == None:
       time.sleep(0.25)
       continue
#    for press in presses:
#        print(commands[press["config"]])

    for press in presses:    
        try:
           cmd=commands[press["config"]]
        except KeyError:
           print("getting KeyError")
           continue
