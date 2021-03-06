#!/usr/bin/env python3

""" MiLight Control Interface

A powerful Python API to control your MiLight LED bulbs and strips (White and RGBW).
Based on the documentation from http://www.limitlessled.com/dev/
"""

import socket
import time
from queue import PriorityQueue
from threading import Thread
import inspect

class DiscoverBridge(object):
    """ WIFI Bridge Auto Discovery

    - Step 1:Send UDP message to the LAN broadcast IP address and port 48899 => "Link_Wi-Fi"
    - All Wifi bridges on the LAN will respond with their details. Response is "10.10.100.254, ACCF232483E8"
    """

    def __init__(self, port=48899, wait_time=5):
        """ init """
        self.port = port
        self.wait_time = wait_time

    def discover(self):
        """ Start discovery """
        bufferSize = 1024
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, True)
        sock.settimeout(self.wait_time)
        sock.sendto(b"Link_Wi-Fi", ("<broadcast>", self.port))
        found = list()
        try:
            message = sock.recv(bufferSize)
            lst = message.decode('utf-8').split(',')
            if not len(lst) % 2:  # should be odd since the string ends with a ','
                print('return values false')
            for i in range(0, int(len(lst)/2)):
                index = i*2
                found.append((lst[index], lst[index + 1]))
        except socket.timeout:
            print("No server found")
        sock.close()
        return found

class Group(object):
    """ Common functions for bulb/strip groups """
    # static record of time that last command was executed
    _last_command_time = time.time() 
    def get_last_time(self):
        return self._last_command_time
    def set_last_time(self, val):
        self._last_command_time = val
    last_command_time = property(get_last_time, set_last_time)
    # static queue for storing commands
    _queue = PriorityQueue()
    def get_queue(self):
        return self._queue
    queue = property(get_queue)
    # static process for handling commands
    _qprocess = Thread()
    def get_process(self):
        return self._qprocess
    qprocess = property(get_process)
    # static variable to indicate if all commands have been processed
    _finished = True
    def get_finished(self):
        return self._finished
    def set_finished(self, val):
        self._finished = val
    finished = property(get_finished, set_finished)
    # initialisation
    def ___init___(self, ip_address, port=8899, pause=0.1, group=None):
        """ init """
        self.ip_address = ip_address
        self.port = port
        if pause <= 0:
            pause = 0.1
        self.pause = pause
        if str(group) in ['1', '2', '3', '4']:
            self.group = str(group)
        else:
            self.group = 'ALL'
        if self.qprocess._target is None:
            self.qprocess._target = self.qworker
            self.qprocess.daemon = True
            self.qprocess.start()
        
    def qworker(self):
        """ Process command queue """
        while True:
            (cmdtime,command,group) = self.queue.get()
            self.finished = False
            if cmdtime is None:
                cmdtime = time.time()
            # Lights require time between commands, 100ms is recommended by the documentation
            pause_remaining = max(cmdtime - time.time(),
                                      (self.pause - (time.time() - self.last_command_time)))
            if pause_remaining > 0:
                time.sleep(pause_remaining)
            # open the connection and send the command(s)
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)                
            if group is not None:
                oncmd = self.GROUP_ON[group] + b"\x00" + b"\x55"
                sock.sendto(oncmd, (self.ip_address, self.port))
                time.sleep(self.pause)    
            self.last_command_time = time.time()
            sock.sendto(command, (self.ip_address, self.port))
            # close the connection and flag if the queue is empty
            sock.close()
            self.queue.task_done()
            if self.queue.empty():
                self.finished = True

    def empty_queue(self, when=None):
        """ Empty the command queue without executing the commands """
        now = time.time()
        if (when is not None) and (when > now):
            time.sleep(when - now)
        while not self.queue.empty():
            self.queue.get()
            self.queue.task_done()

    def send_commands(self, command, steps=1, period=None, pause=None, when=None,
                          interleave=False, byte2=b"\x00", byte3=b"\x55"):
        """ Send \"steps\" repeats of \"command\" with pause of length \"pause\" inbetween, 
        or if \"period\" is given then make pauses long enough so that commands are all sent
        within that amount of time (in seconds). If \"when\" is supplied, only start sending the commands
        at that time. If \"interleave\" is True (its False by default) then interleave commands with calls 
        to \"on\" to ensure that all commands go to the same group number. In this case (interleave = True), 
        the minimum delay between commands (default = 0.1) will be twice as large as normal (so 0.2 by default).
        Optionally increment command with \"byte2\" and \"byte3\". """
        if command is None:
            return
        self.finished = False
        steps = max(1, min(30, steps))  # value should be between 1 and 30
        command += byte2
        command += byte3
        if (pause is None) and (period is None):
            pause = self.pause
        elif period is not None:
            pause = period / steps
        if interleave and (pause < 2*(self.pause)):
            pause = 2*(self.pause)
        if when is None:
            cmdtime = time.time()
        else:
            cmdtime = when
        for i in range(0, steps):
            if interleave or i == 0:
                self.queue.put((cmdtime-self.pause,command,self.group))
            else:
                self.queue.put((cmdtime,command,None))
            cmdtime = cmdtime + pause
        if not interleave:
            self.queue.join()
        return command

    def on(self, when=None):
        """ Switch group on """
        if not self.qprocess.is_alive():
            # make sure we can send commands to the queue
            self.qprocess = Process(target=self.qworker)
            self.qprocess.daemon = True
            self.qprocess.start()
        self.send_commands(command=self.GROUP_ON[self.group], when=when)
        
    def off(self, when=None):
        """ Switch group off """
        self.send_commands(self.GROUP_OFF[self.group], when=when)

            
class ColorGroup(Group):
    """ A group of RGBW color bulbs/strips """
    # Standard ON/OFF
    RGBW_ALL_ON = (66).to_bytes(1, byteorder='big')
    RGBW_ALL_OFF = (65).to_bytes(1, byteorder='big')
    GROUP_1_ON = (69).to_bytes(1, byteorder='big')
    GROUP_1_OFF = (70).to_bytes(1, byteorder='big')
    GROUP_2_ON = (71).to_bytes(1, byteorder='big')
    GROUP_2_OFF = (72).to_bytes(1, byteorder='big')
    GROUP_3_ON = (73).to_bytes(1, byteorder='big')
    GROUP_3_OFF = (74).to_bytes(1, byteorder='big')
    GROUP_4_ON = (75).to_bytes(1, byteorder='big')
    GROUP_4_OFF = (76).to_bytes(1, byteorder='big')

    GROUP_ON = {
        'ALL': RGBW_ALL_ON,
        '1': GROUP_1_ON,
        '2': GROUP_2_ON,
        '3': GROUP_3_ON,
        '4': GROUP_4_ON
    }
    GROUP_OFF = {
        'ALL': RGBW_ALL_OFF,
        '1': GROUP_1_OFF,
        '2': GROUP_2_OFF,
        '3': GROUP_3_OFF,
        '4': GROUP_4_OFF
    }
    # Set to WHITE
    RGBW_ALL_TO_WHITE = (194).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    GROUP_1_TO_WHITE = (197).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    GROUP_2_TO_WHITE = (199).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    GROUP_3_TO_WHITE = (201).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    GROUP_4_TO_WHITE = (203).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON

    GROUP_WHITE = {
        'ALL': RGBW_ALL_TO_WHITE,
        '1': GROUP_1_TO_WHITE,
        '2': GROUP_2_TO_WHITE,
        '3': GROUP_3_TO_WHITE,
        '4': GROUP_4_TO_WHITE
    }
    # Set BRIGHTNESS
    # Byte2: 0x02 to 0x1B (decimal range: 2 to 27) full brightness 0x1B (decimal 27)
    BRIGHTNESS = (78).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    # Set to DISCO
    DISCO_MODE = (77).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    DISCO_SPEED_SLOWER = (67).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    DISCO_SPEED_FASTER = (68).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    # Specials disco
    DISCO_CODE = b"\x42\x00\x40\x40\x42\x00\x4e\x02"
    DISCO_CODES = {
        "RAINBOW": b"\x4d\x00" * 1,
        "WHITE BLINK": b"\x4d\x00" * 2,
        "COLOR FADE": b"\x4d\x00" * 3,
        "COLOR CHANGE": b"\x4d\x00" * 4,
        "COLOR BLINK": b"\x4d\x00" * 5,
        "RED BLINK": b"\x4d\x00" * 6,
        "GREEN BLINK": b"\x4d\x00" * 7,
        "BLUE BLINK": b"\x4d\x00" * 8,
        "DISCO": b"\x4d\x00" * 9
    }
    # Set COLOR
    # Byte2: 0x00 to 0xFF (255 colors) = COLOR_CODE
    COLOR = (64).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    COLOR_CODES = {
        "VIOLET": b"\x00",
        "ROYALBLUE": b"\x10",
        "LIGHTSKYBLUE": b"\x20",
        "AQUA": b"\x30",
        "AQUAMARINE": b"\x40",
        "SEAGREEN": b"\x50",
        "GREEN": b"\x60",
        "LIMEGREEN": b"\x70",
        "YELLOW": b"\x80",
        "GOLDENROD": b"\x90",
        "ORANGE": b"\xA0",
        "RED": b"\xB0",
        "PINK": b"\xC0",
        "FUCHSIA": b"\xD0",
        "ORCHID": b"\xE0",
        "LAVENDER": b"\xF0"
    }
    def __init__(self, ip_address, port=8899, pause=0.1, group=None):
        """ init """
        super().___init___(ip_address, port, pause, group)

    def white(self, when=None):
        """ Switch to white """
        self.send_commands(command=self.GROUP_WHITE[self.group], when=when)

    def brightness(self, value=10, when=None):
        """ Set brightness level """
        value += 2                      # value should be between 0 and 25
        value = max(2, min(27, value))  # value should be between 2 and 27
        self.send_commands(command=self.BRIGHTNESS, when=when, byte2=(value).to_bytes(1, byteorder='big'))

    def disco(self, mode='', when=None):
        """ Enable disco mode, if no valid mode is provided the default disco mode is started """
        if mode.upper() in self.DISCO_CODES:
            command = self.DISCO_CODE + self.DISCO_CODES[mode.upper()]
            self.send_commands(command=command, when=when, byte2=b"", byte3=b"")
        else:
            self.send_commands(comand=self.DISCO_MODE)

    def increase_disco_speed(self, steps=1, period=None, pause=None, when=None, interleave=False):
        """ Increase disco_speed """
        self.send_commands(command=self.DISCO_SPEED_FASTER, steps=steps,
                               period=period, pause=pause, when=when,  interleave=interleave)

    def decrease_disco_speed(self, steps=1, period=None, pause=None, when=None, interleave=False):
        """ Decrease disco_speed """
        self.send_commands(command=self.DISCO_SPEED_SLOWER, steps=steps,
                               period=period, pause=pause, when=when, interleave=interleave)

    def color(self, value, when=None):
        """ Set color """
        colorcode = None
        try:
            cvalue = int(value)
            value = cvalue
        except:
            pass
        if type(value) is bytes:
            if len(value) == 1:
                colorcode = value
            else:
                ValueError('The requested color value in bytes should be between x00 and xFF (= 1 byte), received ' + len(value) + ' bytes')
        elif type(value) is int:
            value = max(0, min(255, value))  # value should be between 0 and 255
            colorcode = (value).to_bytes(1, byteorder='big')
        elif type(value) is str:
            if value.upper() in self.COLOR_CODES:
                colorcode = self.COLOR_CODES[value.upper()]
            else:
                ValueError('The requested color as string should be valid (see self.COLOR_CODES)')
        else:
            raise ValueError('Invalid color requested (supported types: byte, integer, string)')
        if colorcode is not None:
            self.send_commands(command=self.COLOR, when=when, byte2=colorcode)
        else:
            raise ValueError('Invalid color requested (unspecified error, value-type: ' + str(type(value)) + ')')

    def disco_codes(self):
        """ return the disco-codes """
        return [c.lower() for c in self.DISCO_CODES.keys()]

    def color_codes(self):
        """ return the color-codes """
        return [c.lower() for c in self.COLOR_CODES.keys()]

class WhiteGroup(Group):
    """ A group of white bulbs/strips """

    # Standard ON/OFF
    WHITE_ALL_ON = (53).to_bytes(1, byteorder='big')
    WHITE_ALL_OFF = (57).to_bytes(1, byteorder='big')
    GROUP_1_ON = (56).to_bytes(1, byteorder='big')
    GROUP_1_OFF = (59).to_bytes(1, byteorder='big')
    GROUP_2_ON = (61).to_bytes(1, byteorder='big')
    GROUP_2_OFF = (51).to_bytes(1, byteorder='big')
    GROUP_3_ON = (55).to_bytes(1, byteorder='big')
    GROUP_3_OFF = (58).to_bytes(1, byteorder='big')
    GROUP_4_ON = (50).to_bytes(1, byteorder='big')
    GROUP_4_OFF = (54).to_bytes(1, byteorder='big')

    GROUP_ON = {
        'ALL': WHITE_ALL_ON,
        '1': GROUP_1_ON,
        '2': GROUP_2_ON,
        '3': GROUP_3_ON,
        '4': GROUP_4_ON
    }
    GROUP_OFF = {
        'ALL': WHITE_ALL_OFF,
        '1': GROUP_1_OFF,
        '2': GROUP_2_OFF,
        '3': GROUP_3_OFF,
        '4': GROUP_4_OFF
    }
    # Standard BRIGHTNESS/WHITE-COLOR
    BRIGHTNESS_UP = (60).to_bytes(1, byteorder='big')
    BRIGHTNESS_DOWN = (52).to_bytes(1, byteorder='big')
    WARM_WHITE_INCREASE = (62).to_bytes(1, byteorder='big')
    COOL_WHITE_INCREASE = (63).to_bytes(1, byteorder='big')
    # Specials FULL_BRIGHTNESS/NIGHT_MODE
    FULL_BRIGHTNESS_ALL = (181).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    FULL_BRIGHTNESS_GROUP_1 = (184).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    FULL_BRIGHTNESS_GROUP_2 = (189).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    FULL_BRIGHTNESS_GROUP_3 = (183).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    FULL_BRIGHTNESS_GROUP_4 = (178).to_bytes(1, byteorder='big')  # send 100ms after GROUP_ON
    # send 100ms after GROUP_OFF
    NIGHT_MODE_ALL = (185).to_bytes(1, byteorder='big')
    NIGHT_MODE_GROUP_1 = (187).to_bytes(1, byteorder='big')  # send 100ms after GROUP_OFF
    NIGHT_MODE_GROUP_2 = (179).to_bytes(1, byteorder='big')  # send 100ms after GROUP_OFF
    NIGHT_MODE_GROUP_3 = (186).to_bytes(1, byteorder='big')  # send 100ms after GROUP_OFF
    NIGHT_MODE_GROUP_4 = (182).to_bytes(1, byteorder='big')  # send 100ms after GROUP_OFF

    FULL_BRIGHTNESS = {  # send 100ms after GROUP_ON
        'ALL': FULL_BRIGHTNESS_ALL,
        '1': FULL_BRIGHTNESS_GROUP_1,
        '2': FULL_BRIGHTNESS_GROUP_2,
        '3': FULL_BRIGHTNESS_GROUP_3,
        '4': FULL_BRIGHTNESS_GROUP_4
    }
    NIGHT_MODE = {  # send 100ms after GROUP_OFF
        'ALL': NIGHT_MODE_ALL,
        '1': NIGHT_MODE_GROUP_1,
        '2': NIGHT_MODE_GROUP_2,
        '3': NIGHT_MODE_GROUP_3,
        '4': NIGHT_MODE_GROUP_4
    }

    def __init__(self, ip_address, port=8899, pause=0.1, group=None):
        """ init """
        super().___init___(ip_address, port, pause, group)

    def increase_brightness(self, steps=1, period=None, pause=None, when=None, interleave=False):
        """ Increase brightness """
        self.send_commands(self.BRIGHTNESS_UP, steps=steps, period=period, pause=pause,
                               when=when, interleave=interleave)

    def decrease_brightness(self, steps=1, period=None, pause=None, when=None, interleave=False):
        """ Decrease brightness """
        self.send_commands(self.BRIGHTNESS_DOWN, steps=steps, period=period, pause=pause,
                               when=when, interleave=interleave)

    def increase_warmth(self, steps=1, period=None, pause=None, when=None, interleave=False):
        """ Increase warmth """
        self.send_commands(self.WARM_WHITE_INCREASE, steps=steps,  period=period, pause=pause,
                               when=when, interleave=interleave)

    def decrease_warmth(self, steps=1, period=None, pause=None, when=None, interleave=False):
        """ Decrease warmth """
        self.send_commands(self.COOL_WHITE_INCREASE, steps=steps, period=period, pause=pause, 
                               when=when, interleave=interleave)

    def brightmode(self, when=None):
        """ Enable full brightness """
        self.send_commands(self.FULL_BRIGHTNESS[self.group], when=when)

    def nightmode(self, when=None):
        """ Enable nightmode """
        self.send_commands(self.NIGHT_MODE[self.group], when=when)

def apply2grps(grps, fn, delay=0, args=None):
    """ Call member function \"fn\" on each Group object in \"grps\" (in order)
with arguments \"args\", and with a pause of \"delay\" seconds in between each call. 
E.g: apply2grps([grp1,grp2,grp3],\"increase_brightness\",1,[10,5,None,None,True])
If args contains a value for \"when\" then the delay will be consecutively added to 
this time. """
    if args is None:
        args = []
    if type(args) in [tuple, list]:
        args = dict(zip(inspect.getargspec(getattr(grps[0], fn)).args, args))
    if 'when' in args:
        exectime = args.pop('when')
        if exectime is None:
            exectime = time.time()
    else:
        exectime = time.time()
    for grp in grps:
        grpfn = getattr(grp, fn)
        args['when'] = exectime
        grpfn(**args)
        exectime = exectime + delay

