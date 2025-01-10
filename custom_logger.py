import locale
import sys
import logging
from datetime import datetime, timedelta
import pathlib

locale.setlocale(locale.LC_TIME, 'fr_CA')
LOGGER_FORMAT="delta"
#LOGGER_FORMAT=None

class CustomFormatter(logging.Formatter):
    white = "\x1b[37m"
    bold_white = "\x1b[37;1m"
    yellow = "\x1b[33m"
    bold_yellow = "\x1b[37;1m"
    red = "\x1b[31m"
    underlined_red = "\x1b[31;21m"
    reversed_red = "\x1b[31;7m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[34m"
    reset = "\x1b[0m"
    if LOGGER_FORMAT is None:
        LOGGER_FORMAT= "time"
    if LOGGER_FORMAT == "delta":
        format = '[%(delta)-8s][%(name)-15s:%(lineno)4d][%(levelname)-8s] %(message)s'
    else:
        format = '[%(asctime)s][%(name)-15s:%(lineno)4d][%(levelname)-8s] %(message)s'

    FORMATS= { 
        logging.DEBUG: bold_white + format + reset,
        logging.INFO: blue + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: bold_red + format + reset,
        logging.CRITICAL: reversed_red + format + reset
    }

    def format(self, record):
        #Elapsed time
        duration= datetime.utcfromtimestamp(record.relativeCreated / 1000)
        record.delta = duration.strftime("%H:%M:%S")

        log_fmt= self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
    
logger = logging.getLogger()
root_logger = logger
if logger.name == 'root' and len(sys.argv[0]) > 0:
    arg_zero = pathlib.Path(sys.argv[0])
    logger= logger.getChild(arg_zero.stem)
else:
    root_logger= logger.root

root_logger.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(CustomFormatter())
root_logger.addHandler(ch)
