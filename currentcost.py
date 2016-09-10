#!/usr/bin/python3
# sudo apt-get update
# sudo apt-get install python3-pip
# sudo pip3 install untangle
# sudo pip3 install pyserial

__author__ = 'rarosalion'


import untangle
import serial
import urllib.request
import logging
import os
import sys
import xml

# CONFIG
LOG_FILENAME = os.path.dirname(os.path.realpath(__file__)) + '/data/currentcost.log'
API_KEY = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
RETRIES = 100
SERIAL_PORT = '/dev/ttyUSB0'
EMONCMS_URL = 'http://localhost'
IGNORE=['src', 'dsb', 'time', 'sensor', 'id', 'type'] # Tags to ignore in the XML
SUM_TOTAL_POWER = ['ch1', 'ch2', 'ch3'] # Sum these channels for total power

# LOGGER SETUP
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# Create logging handlers
fh = logging.FileHandler(LOG_FILENAME)
fh.setLevel(logging.ERROR)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# create formatter and add it to the handlers
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
fh.setFormatter(formatter)
ch.setFormatter(formatter)
# add the handlers to the logger
logger.addHandler(fh)
logger.addHandler(ch)

logger.debug("Logging debug messages")
logger.info("Logging info messages")
logger.error("Logging error messages")


class DataException(Exception):
    pass

def get_data(port=SERIAL_PORT):
    """Gets raw XML data from attached CurrentCost meter.
    Parameters:
     - port: the port that the CurrentCost meter is attached to. Somthing like /dev/ttyUSB0 or COM1
    Returns:
    string with raw XML data
    """
    for attempt in range(RETRIES):
        logger.debug("Attempting to read data %d/%d" % (attempt, RETRIES))
        try:
            ser = serial.Serial(port, 57600)
            xmldata = ser.readline().decode('utf-8')
            ser.close()
            logger.debug(xmldata)
            return xmldata
            break
        except IOError:
            logger.error("Error reading data from %s (attempt %d/%d" % (port, attempt, RETRIES))
        if (attempt == RETRIES):
            return False

    return False

def parse_data(xmldata):
    """Parses XML data from the currentcost device
    Parameters:
    - xmldata: string containing valid xml data
    Returns:
    - list with strings containing 'name:value' pairs
    """
    # Parse XML
    try:
        p = untangle.parse(xmldata)
        children = p.msg.children
    except xml.sax.SAXParseException:
        logger.error("Problem parsing XML data: %s" % xmldata)
        return None
    except (IndexError, AttributeError):
        logger.error("XML did not contain a valid message: %s" % xmldata)
        return None

    # Create json-ish list of values
    retlist = []
    totalwatts = 0
    for obj in children:
        if obj._name in IGNORE: continue
        name = 'temp' if obj._name == 'tmpr' else obj._name # Replace 'tmpr' with 'temp'
        try:
            value = float(obj.watts.cdata)
        except (IndexError, AttributeError):
            value = float(obj.cdata)
        if name in SUM_TOTAL_POWER: totalwatts += value # Sum relevant channels to 'totalwatts'
        retlist += ["%s:%.2f" % (name, value)]

    # Finalise list, and return
    retlist += ["power:%.2f" % totalwatts]
    return retlist


def get_and_upload_data():
    xmldata = get_data()
    valuelist = parse_data(xmldata)
    logger.info(valuelist)
    for attempt in range(RETRIES):
        logger.debug("Attempting to post data to %s (%d/%d)" % (EMONCMS_URL, attempt, RETRIES))
        try:
            url = "%s/input/post.json?node=1&apikey=%s&json={%s}" % (EMONCMS_URL, API_KEY, ','.join(valuelist))
            urllib.request.urlopen(url)
            break
        except Exception as e:
            logger.error("Error uploading results: %s %d/%d" % (e, attempt, RETRIES))

if __name__ == "__main__":
    while True:
        get_and_upload_data()
        """try:
            get_and_upload_data()
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logger.error("%s - %s:%s" % (exc_type, fname, exc_tb.tb_lineno))
	"""
