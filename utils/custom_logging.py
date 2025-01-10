import os
import logging
import time
import sys
import gradio as gr
from rich.theme import Theme
from rich.logging import RichHandler
from rich.console import Console
from rich.pretty import install as pretty_install
from rich.traceback import install as traceback_install

log = None

def get_logger(logger_name: str):
    if log is None:
        setup_rich_logging()
    return log.getChild(logger_name)

def setup_std_logging():
    global log
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(pathname)s | %(message)s', filename='setup.log', filemode='a', encoding='utf-8', force=True)
    ch= logging.StreamHandler(stream= sys.stdout)
    ch.setLevel(logging.DEBUG)
    
    log= logging.getLogger("sd")
    log.addHandler(ch)
    return log

def setup_rich_logging():
    global log
    if log is not None:
        return log

    rich_handler= RichHandler(rich_tracebacks=True, tracebacks_suppress=[gr])
    logging.basicConfig(
        level=logging.INFO,
        format="[%(module)-15s] %(message)s",
        datefmt="[%X]",
        handlers=[rich_handler]
    )

    log = logging.getLogger("app")
    log.setLevel(logging.DEBUG)
    return log

def setup_logging(clean=False, debug=False):
    global log
    
    if log is not None:
        return log
    
    try:
        if clean and os.path.isfile('setup.log'):
            os.remove('setup.log')
        time.sleep(0.1) # prevent race condition
    except:
        pass
    
    if sys.version_info >= (3, 9):
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(pathname)s | %(message)s', filename='setup.log', filemode='a', encoding='utf-8', force=True)
    else:
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(levelname)s | %(pathname)s | %(message)s', filename='setup.log', filemode='a', force=True)
    
    console = Console(log_time=True, log_time_format='%H:%M:%S-%f', theme=Theme({
        "traceback.border": "black",
        "traceback.border.syntax_error": "black",
        "inspect.value.border": "black",
    }))
    pretty_install(console=console)
    #traceback_install(console=console, extra_lines=1, width=console.width, word_wrap=False, indent_guides=False, suppress=[])
    rh = RichHandler(show_time=True, omit_repeated_times=False, show_level=True, show_path=False, markup=False, rich_tracebacks=True, log_time_format='%H:%M:%S-%f', level=logging.DEBUG if debug else logging.INFO, console=console)
    #rh.set_name(logging.DEBUG if debug else logging.INFO)
    root_logger= logging.RootLogger(logging.INFO)
    root_logger.addHandler(rh)
    log = root_logger.getChild("sd")
    log.setLevel(logging.DEBUG if debug else logging.INFO)
#    log.addHandler(rh)
    
    return log
