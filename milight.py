#!/usr/bin/python3
# -*- coding: utf-8 -*-
""" MiLight Commandline Interface """

import argparse
import mci
import time
import subprocess

def main():
    """ Main. """
    # Parse commandline arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-S', '--scan', action='store_true', dest='scan',
                        help='Search wifi bridges.', default=False, required=False)

    parser.add_argument('-i', '--ip_address', action='store', nargs='?', dest='address',
                        help='IP address.', default='10.0.0.60', required=False, type=str)
    parser.add_argument('-P', '--port', action='store', nargs='?', dest='port',
                        help='Port number.', default=8899, required=False, type=int)

    parser.add_argument('-c', '--rgbw', action='store', dest='rgbw',
                        help='Set RGBW target group, default: None (1, 2, 3, 4, ALL)', default=None, required=False)
    parser.add_argument('-w', '--white', action='store', dest='white',
                        help='Set White target group, default: None (1, 2, 3, 4, ALL)', default=None, required=False)

    parser.add_argument('-a', '--action', action='store', dest='action',
                        help='The desired action, default: None (for white bulbs/strips: ON, OFF, INC_BRIGHTNESS, DEC_BRIGHTNESS, INC_WARMTH, DEC_WARMTH, BRIGHT_MODE, NIGHT_MODE | for rgbw bulbs/strips: ON, OFF, DISCO_MODE, INC_DISCO_SPEED, DEC_DISCO_SPEED)', default=None, required=False)
    parser.add_argument('-s', '--steps', action='store', dest='steps', type=int,
                            help='Number of steps to perform for given action (default=1)', default=1, required=False)
    parser.add_argument('-p', '--pause', action='store', dest='pause', type=float,
                            help='Pause between steps, in seconds (minimum=default=0.1)', default=0.1, required=False)
    parser.add_argument('-t', '--period', action='store', dest='period', type=float,
                            help='Period of time (in seconds) over which steps should be performed (default=1)', default=None, required=False)
    # TODO: accept a time as a string for the --when argument
    parser.add_argument('-W', '--when', action='store', dest='when', default=None, required=False,
                            help='Time at which command should be executed. Can be any string accepted by the linux "date" command (default=now)')
    parser.add_argument('--on', action='store_true', dest='action_on',
                        help='Action: ON', default=False, required=False)
    parser.add_argument('--off', action='store_true', dest='action_off',
                        help='Action: OFF', default=False, required=False)

    parser.add_argument('--ew', action='store_true', dest='action_ew',
                        help='Action (rgbw bulbs/strips only): WHITE', default=False, required=False)
    parser.add_argument('--br', action='store', nargs='?', dest='action_br',
                        help='Action (rgbw bulbs/strips only): set brightness (0 <= value <= 25)', default=None, required=False, type=int)
    parser.add_argument('--cc', action='store', nargs='?', dest='action_cc',
                        help='Action (rgbw bulbs/strips only): set color (int: 0 <= value <= 255)', default=None, required=False)
    parser.add_argument('--d', action='store_true', dest='action_d',
                        help='Action (rgbw bulbs/strips only): DISCO_MODE', default=False, required=False)
    parser.add_argument('--id', action='store_true', dest='action_id',
                        help='Action (rgbw bulbs/strips only): INC_DISCO_SPEED', default=False, required=False)
    parser.add_argument('--dd', action='store_true', dest='action_dd',
                        help='Action (rgbw bulbs/strips only): DEC_DISCO_SPEED', default=False, required=False)

    parser.add_argument('--ib', action='store_true', dest='action_ib',
                        help='Action (white bulbs/strips only): INC_BRIGHTNESS', default=False, required=False)
    parser.add_argument('--db', action='store_true', dest='action_db',
                        help='Action (white bulbs/strips only): DEC_BRIGHTNESS', default=False, required=False)
    parser.add_argument('--iw', action='store_true', dest='action_iw',
                        help='Action (white bulbs/strips only): INC_WARMTH', default=False, required=False)
    parser.add_argument('--dw', action='store_true', dest='action_dw',
                        help='Action (white bulbs/strips only): DEC_WARMTH', default=False, required=False)
    parser.add_argument('--b', action='store_true', dest='action_b',
                        help='Action (white bulbs/strips only): BRIGHT_MODE', default=False, required=False)
    parser.add_argument('--n', action='store_true', dest='action_n',
                        help='Action (white bulbs/strips only): NIGHT_MODE', default=False, required=False)
    parser.set_defaults(steps=1, period=None, pause=0.1, when=None)
    args = parser.parse_args()
    address = args.address
    port = args.port

    # Scan for wifi bridges (to find the ip address)
    if args.scan:
        print('Discovering bridges')
        dg = mci.DiscoverBridge(port=48899).discover()
        for (addr, mac) in dg:
            print(' - ip address :' + addr + '\tmac: ' + mac)

    # Set the requested actions
    action_on = args.action_on
    action_off = args.action_off
    # ColourGroup actions
    action_ew = args.action_ew
    action_br = args.action_br
    action_cc = args.action_cc
    action_d = args.action_d
    action_id = args.action_id
    action_dd = args.action_dd
    # WhiteGroup actions
    action_ib = args.action_ib
    action_db = args.action_db
    action_iw = args.action_iw
    action_dw = args.action_dw
    action_b = args.action_b
    action_n = args.action_n
    # convert "when" argument to float if present
    if args.when is not None:
        args.when = float(subprocess.check_output("date +%s --date " + args.when, shell=True))
        
    if args.action is not None:
        if args.action == 'ON':
            action_on = True
        elif args.action == 'OFF':
            action_off = True
        elif args.action == 'WHITE':
            action_ew = True
        elif args.action == 'DISCO_MODE':
            action_d = True
        elif args.action == 'INC_DISCO_SPEED':
            action_id = True
        elif args.action == 'DEC_DISCO_SPEED':
            action_dd = True
        elif args.action == 'INC_BRIGHTNESS':
            action_ib = True
        elif args.action == 'DEC_BRIGHTNESS':
            action_db = True
        elif args.action == 'INC_WARMTH':
            action_iw = True
        elif args.action == 'DEC_WARMTH':
            action_dw = True
        elif args.action == 'BRIGHT_MODE':
            action_b = True
        elif args.action == 'NIGHT_MODE':
            action_n = True
        else:
            print('Requested action invalid: ' + args.action)

    # Execute action rgbw bulbs/strips
    if args.rgbw is not None:
        # Set the groupnumber
        group = None
        if args.rgbw in ['1', '2', '3', '4']:
            group = int(args.rgbw)
        lc = mci.ColorGroup(address, port, group=group)
        if action_on:
            lc.on()
        if action_off:
            lc.off()
        if action_ew:
            lc.white()
        if action_br is not None:
            lc.brightness(int(action_br), when=args.when)
        if action_cc is not None:
            lc.color(action_cc, when=args.when)
        if action_d:
            lc.disco(when=args.when)
        if action_id:
            lc.increase_disco_speed(steps=args.steps, period=args.period, pause=args.pause, when=args.when)
        if action_dd:
            lc.decrease_disco_speed(steps=args.steps, period=args.period, pause=args.pause, when=args.when)

    # Execute action White bulbs/strips
    if args.white is not None:
        # Set the groupnumber
        group = None
        if args.white in ['1', '2', '3', '4']:
            group = int(args.white)
        lc = mci.WhiteGroup(address, port, group=group)
        if action_on:
            lc.on()
        if action_off:
            lc.off()
        if action_ib:
            lc.increase_brightness(steps=args.steps, period=args.period, pause=args.pause, when=args.when)
        if action_db:
            lc.decrease_brightness(steps=args.steps, period=args.period, pause=args.pause, when=args.when)
        if action_iw:
            lc.increase_warmth(steps=args.steps, period=args.period, pause=args.pause, when=args.when)
        if action_dw:
            lc.decrease_warmth(steps=args.steps, period=args.period, pause=args.pause, when=args.when)
        if action_b:
            lc.brightmode(when=args.when)
        if action_n:
            lc.nightmode(when=args.when)
            
    while not lc.finished:
        time.sleep(0.1)

if __name__ == '__main__':
    main()
