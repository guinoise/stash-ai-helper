from stashapi.stashapp import StashInterface
from stashapi.stashbox import StashBoxInterface
from custom_logger import logger
import logging
from datetime import datetime
import pathlib
import json
import yaml
import argparse as ap
import string
from dataclasses import dataclass
import typing
import requests
from Objects import Performer
import Utils


safechars = string.ascii_lowercase + string.ascii_uppercase + string.digits + '.-_'
def to_safechars(input: str) -> str:
    return ''.join([c for c in input if c in safechars])

def main():
    logger.info("Script %s", __file__)
    logger.info("Start time: {0:%Y-%m-%d %H:%M:%S} UTC".format(datetime.now()))

    parser = ap.ArgumentParser(
        description="Get scene from stash and save into json file",
        formatter_class=ap.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--debug", action="store_true", help="Log level to DEBUG")
    parser.add_argument(
        "--warning", "--warn", action="store_true", help="Log level to WARNING"
    )
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
    # else:
    #     logging.getLogger("StashLogger").setLevel(logging.WARNING)
    if args.warning:
        logger.setLevel(logging.WARNING)

    base_dir = pathlib.Path(__file__).parent.resolve()

    config_file= base_dir.joinpath('config.json')    
    if not config_file.is_file():
        logger.critical(f"Configuration file {config_file.resolve()} does not exists. Run the gui.py and configure through Config tab.")
        return 1
    with config_file.open('rb') as fp:
        config= json.load(fp)
    if config.get('stash_api_key', '') == 'ABCV':
        stash = StashInterface({
            "scheme": config.get('stash_schema'),
            "host": config.get('stash_hostname'),
            "port": config.get('stash_port'),
            "logger": logger
        })
    else:
        stash = StashInterface({
            "scheme": config.get('stash_schema'),
            "host": config.get('stash_hostname'),
            "port": config.get('stash_port'),
            "ApiKey": config.get('stash_api_key'),
            "logger": logger
        })
    logger.info("Configuration")
    conf= stash.get_configuration()
    logger.debug(json.dumps(conf, indent=2))
    debug_json_file= base_dir.joinpath('debug.json')
    with debug_json_file.open('w') as fp:
        json.dump(stash.get_configuration(), fp, indent=2)
        logger.info(f"Config in debug file : {debug_json_file.relative_to(base_dir)}")
    logger.info(f"Stash boxes: \n{json.dumps(conf.get('general', {}).get('stashBoxes', []), indent=2)}")
    return 0


if __name__ == "__main__":
    return_code = 0
    try:
        return_code = main()
    except KeyboardInterrupt:
        logger.critical("CTRL-C")
    except Exception as e:
        logger.critical(f"Unhandled exception : {e!s}")
        logger.exception(f"{e!s}", e)
        exit(254)
    finally:
        pass
    exit(return_code)
