#! /usr/bin/python3 -u



import os
import dbus
import dbus.mainloop.glib
import faulthandler
import signal
import sys
import time
import json

from argparse import ArgumentParser
from gi.repository import GLib

from p8s_writer import P8sWriter
from dbus_meter import DbusMeter

import logging
log = logging.getLogger(__name__)

NAME = os.path.basename(__file__)
VERSION = '1.0'




def main():
    parser = ArgumentParser(add_help=True)
    parser.add_argument('-d', '--debug', help='enable debug logging',
                        action='store_true')
    parser.add_argument('-c', '--config', help='configfile', action='append', default='config.json')
    parser.add_argument('-s', '--secrets', help='secrets', action='append', default='secrets.json')
    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s %(levelname)s %(name)-10s %(message)s',
                        level=(logging.DEBUG if args.debug else logging.INFO))


    log.info(f'{NAME} v{VERSION}')

    signal.signal(signal.SIGINT, lambda s, f: os._exit(1))
    faulthandler.register(signal.SIGUSR1)
    faulthandler.enable()




    dbus.mainloop.glib.threads_init()
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)


    with open(args.config) as stream:
        config = json.load(stream)
    with open(args.secrets) as stream:
        secrets = json.load(stream)

    meters = DbusMeter(config)
    writer = P8sWriter('frog', meters,  secrets['p8s'])
    writer.update()


    mainloop = GLib.MainLoop()
    GLib.timeout_add_seconds(60, writer.update)
    mainloop.run()

if __name__ == '__main__':
    main()