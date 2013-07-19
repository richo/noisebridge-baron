#!/usr/bin/python

# noisebridge-baron
#
# Interfaces with the pay phone keypad at the entrance to Noisebridge,
# opening the gate for those who know one of the entry codes.  Requires
# the python-serial (pyserial) module.
#
# Authors have included:
#   davidme
#   jesse
#   mct

import urllib, urllib2, json
import logging
import serial
import argparse
import sys
import os

from time import sleep

keypad = None
codes_path = None
codes = []
promiscuous = False

def open_serial(filename):
    global keypad

    try:
        logging.debug("Opening %s", filename)
        keypad = serial.Serial(filename, 300, bytesize=serial.EIGHTBITS,
                               parity=serial.PARITY_NONE,
                               stopbits=serial.STOPBITS_ONE,
                               xonxoff=0,
                               rtscts=0,
                               writeTimeout=10)
    #except serial.serialutil.SerialException as e:
    except Exception as e:
        logging.error("Serial port setup failed: %s: %s: %s", filename, type(e), str(e))
        raise

last_mtime = 0
def load_codes(filename=None):
    """
    Loads a list of valid access codes from the specified filename.  Lines
    starting with '#' are comments.  All other lines must contain numeric codes
    which grant access, one code per line.

    Each time this function is called, it will only re-open the codes file it's
    mtime since the last call has changed.
    """

    global codes_path, codes, last_mtime

    if not filename:
        filename = codes_path

    try:
        mtime = os.stat(filename).st_mtime
        if mtime == last_mtime:
            logging.debug("mtime has not changed, not reloading %s", filename)
            return
        else:
            last_mtime = mtime

        new_codes = []
        for lineno, line in enumerate(open(filename)):
            code = line.split("#")[0].strip().rstrip()
            if not code:
                continue
            if not code.isdigit():
                logging.warning("%s:%d: Ignoring malformed line" % (filename, lineno))
            new_codes.append(code)

        logging.info("Loaded %d codes from %s" % (len(new_codes), filename))
        codes = new_codes

    except Exception as e:
        logging.error("Error loading %s: %s: %s" % (filename, type(e), str(e)))
        raise

def open_gate(endpoint='http://api.noisebridge.net/gate/', command={'open':1}):
    """
    Uses the Noisebridge API to open the front gate.
    """
    try:
        results = urllib2.urlopen(endpoint, urllib.urlencode(command)).read()
        results = json.loads(results)
    except urllib2.HTTPError, e:
        logging.error("error: HTTP Error %s when calling <%s>: %s" % (endpoint, e.code, e.read()))
        return False
    except urllib2.URLError, e:
        logging.error("error: Could not reach <%s> data is %s" % (endpoint, e.args))
        return False
    except ValueError:
        logging.error("error: Could not decode JSON from <%s>: %r" % results)
        return False

    if results.get('open', False):
        return True
    else:
        return False

def check_code(code, reload_codes=True):
    global codes

    if reload_codes:
        load_codes()

    if code and code in codes:
        logging.info("Opening the door for code %s" % code)

        if open_gate():
            keypad.write('BH')  # Blue LED, Happy sound
        else:
            keypad.write('SR')  # Sad sound, Red LED
            sleep(0.2)
            keypad.write('QSR') # Quiet, Sad sound, Red LED
            sleep(0.2)
            keypad.write('QSR') # Quiet, Sad sound, Red LED
    else:
        logging.info("Not opening the door for bad code %s" % code)
        keypad.write('SR') # Sad sound, Red LED

def send_debug(buf):
    global keypad
    logging.debug("Sending %s" % repr(buf))
    keypad.write(buf)

def do_test():
    global codes

    send_debug('SR'); sleep(1) # Sad Red
    send_debug('SG'); sleep(1) # Sad Green
    send_debug('SB'); sleep(1) # Sad Blue
    send_debug('Q');  sleep(1) # Quiet
    send_debug('HR'); sleep(1) # Happy Red
    send_debug('HG'); sleep(1) # Happy Green
    send_debug('HB'); sleep(1) # Happy Blue

    codes = ["42"]
    check_code("42", reload_codes=False)

def door_loop():
    global keypad

    # Specify a timeout with pyserial, to have read() return after N seconds
    # with no input.  If the keypad is idle for this long, we'll detect it by
    # reading zero bytes, and clear the input buffer.
    keypad.timeout = 10

    input_buffer = ""

    while True:
        try:
            char = keypad.read(1)

            if not char:
                logging.debug("Keypad read timeout, flushing input buffer")
                input_buffer = ""
                continue

            if promiscuous:
                logging.info("Opening door in promiscuous mode")
                open_gate()
                continue

            if char == "*":
                logging.debug("Read character %s, flushing input buffer", repr(char))
                input_buffer = ""

            elif char == "#":
                if not input_buffer:
                    logging.debug("Read character %s, but ignoring empty code", repr(char))
                else:
                    logging.debug("Read character %s, checking code", repr(char))
                    check_code(input_buffer)
                input_buffer = ""

            elif char.isdigit():
                logging.debug("Read character %s", repr(char))
                input_buffer += char

            else:
                logging.debug("Ignoring non-digit character: %s" % repr(char))

        except Exception as e:
            logging.error("Keypad error: %s: %s" % (type(e), str(e)))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port",       required=True,          help="Serial port")
    parser.add_argument("--codefile",   required=True,          help="File containing list of valid access codes")
    parser.add_argument("--logfile",    default=None,           help="Write output to logfile, rather than standard out")
    parser.add_argument("--debug",      action="store_true",    help="Enable debugging output")
    parser.add_argument("--test",       action="store_true",    help="Execute single-shot keypad output test")
    parser.add_argument("--promiscuous",action="store_true",    help="Enable any keypress at all to open the door")
    parser.add_argument("--daemon",     action="store_true",    help="Daemonize the baron process")
    parser.add_argument("--instance",   default=None,           help="Name this baron instance, if there are more than one instance")
    parser.add_argument("--pidfile",    default=None,           help="Name the pidfile that should store the daemon pid")
    args = parser.parse_args()

    codes_path = args.codefile
    promiscuous = args.promiscuous
    if args.instance is None:
      args.instance = "default"
    if args.pidfile is None:
      args.pidfile = "/var/run/baron_%s.pid" % args.instance

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(format='%(asctime)s %(levelname)-7s %(message)s', datefmt='%Y-%m-%d %H:%M:%S', level=level, filename=args.logfile)

    try:
        open_serial(args.port)
    except:
        logging.error("Serial port setup failed.  Exiting.")
        sys.exit(1)

    if args.test:
        do_test()
        sys.exit()


    if args.daemon:
      try:
        pid = os.fork()
        if pid > 0:
          # exit first parent
          sys.exit(0)
      except OSError, e:
        print >>sys.stderr, "fork #1 failed: %d (%s)" % (e.errno, e.strerror)
        sys.exit(1)

      # decouple from parent environment
      os.chdir("/")
      os.setsid()
      os.umask(0)

      # do second fork
      try:
          pid = os.fork()
          if pid > 0:
              # exit from second parent, print eventual PID before
              print "Daemon PID %d" % pid
              f = open(args.pidfile, "w")
              f.seek(0)
              f.write(str(pid) + "\n")
              f.close()
              sys.exit(0)
      except OSError, e:
          print >>sys.stderr, "fork #2 failed: %d (%s)" % (e.errno, e.strerror)
          sys.exit(1)
      # start the daemon main loop

    logging.info("Starting Baron")
    load_codes()
    door_loop()
