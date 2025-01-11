#import stashapi.log as log
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

    parser.add_argument("--stash-config-file", "--stash-config", "--sc", type=pathlib.Path, action='store', help='Stash configuration file', default='config.yml')
    parser.add_argument("--stash-box", "-s", type=str, action='store', required=True, help='Stash box name to connect to (from stash-config). Use ? as value to list.')
    parser.add_argument("--debug", action="store_true", help="Log level to DEBUG")
    parser.add_argument("--refresh", action="store_true", help='Refresh metadata from stash box')
    parser.add_argument(
        "--warning", "--warn", action="store_true", help="Log level to WARNING"
    )
    parser.add_argument('--performer', '-p', nargs='+', type=str, action='store', required=True, help='ID of performer(s) in stash box')
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
    # else:
    #     logging.getLogger("StashLogger").setLevel(logging.WARNING)
    if args.warning:
        logger.setLevel(logging.WARNING)

    base_dir = pathlib.Path(__file__).parent.resolve()
    
    logger.info(f"Stash config file : {args.stash_config_file.resolve()}")
    if not args.stash_config_file.exists():
        logger.critical(f"Config file {args.stash_config_file.resolve()} does not exists")
        return 1
    with args.stash_config_file.open('r') as f:
        stash_config= yaml.load(f, Loader=yaml.FullLoader)
    stash_boxes=stash_config.get('stash_boxes', [{}])
    if args.stash_box == "?":
        for sb in stash_boxes:
            logger.warning(f"Stash box name: {sb.get('name')}")
        return 0
    stash_box= None
    for sb in stash_boxes:
        if args.stash_box.casefold() == sb.get('name', '').casefold():
            logger.info(f"Stash box {sb.get('name')} at {sb.get('endpoint')}")
            sb["safe_name"]= to_safechars(sb.get('name'))
            logger.debug(f"Stash box safe name : {sb.get('safe_name')}")
            stash_box= sb
            break
    
    if stash_box is None:
        logger.error(f"Unable to load stash box configuration {args.stash_box}. Valids names below.")
        for sb in stash_boxes:
            logger.warning(f"Stash box name: {sb.get('name')}")
        return 1
    
    performers_dir= base_dir.joinpath('performers')

    if not performers_dir.is_dir():
        logger.warning(f"Create performers dir : {performers_dir.resolve()}")
        performers_dir.mkdir(parents=True)
    
    performers: typing.List[Performer]=[]
    need_download_metadata: bool= False

    for performer_id in args.performer:
        safe_name= f"{sb.get('safe_name')}_{performer_id}"
        performer: Performer= Performer(performer_id, 
                                        sb.get('name'), 
                                        safe_name, 
                                        performers_dir.joinpath(f"{safe_name}.json"), 
                                        performers_dir.joinpath(f"{safe_name}_stash_images"), 
                                        True)
        performers.append(performer)
        if not Utils.load_metadata_file_for_performer(performer) or args.refresh:
            performer.download_metadata= True
            need_download_metadata= True

    logger.debug(performers)    
    logger.debug(f"Need download: {need_download_metadata}")
    logger.debug(f"Nb performers: {len(performers)} {args.performer}")
    if need_download_metadata:
        box= StashBoxInterface({"endpoint": sb.get('endpoint'), "api_key": sb.get('apikey')})
        performer: Performer
        for performer in performers:
            metadata= box.find_performer(performer.id)
            if metadata is None:
                logger.warning(f"Performer {performer.id} not found in {sb.get('name')}")
            else:
                performer.metadata= metadata
                logger.info(f"Metadata downloaded for {performer.id} {metadata.get('name')} saved to {performer.metadata_file.name}")
                Utils.save_performer(performer)

    performer: Performer
    for performer in performers:
        if performer.metadata is None:
            logger.warning(f"Performer id {performer.id} has not metadata. Skip images download")
            continue
        if not performer.stash_box_images_dir.exists():
            logger.debug(f"Create image folder : {performer.stash_box_images_dir.relative_to(base_dir)}")
            performer.stash_box_images_dir.mkdir()

        for image_metadata in performer.metadata.get('images', []):
            logger.debug(image_metadata)
            image_path= performer.stash_box_images_dir.joinpath(image_metadata.get('id'))
            image_metadata_path= performer.stash_box_images_dir.joinpath(f"{image_metadata.get('id')}.json")
            if not image_path.exists() or not image_metadata_path.exists():
                try:
                    logger.info(f"Downloading image from {image_metadata.get('url')}")
                    response= requests.get(image_metadata.get('url'))
                    with image_path.open('wb') as handler:
                        handler.write(response.content)
                    if image_metadata.get('content-type') is None or image_metadata['content-type'] != response.headers['content-type']:
                        image_metadata['content-type']= response.headers['content-type']
                    with image_metadata_path.open('w') as f:
                        json.dump(image_metadata, f, indent=2)                        
                except Exception as e:
                    logger.error(f"Error downloading image from {image_metadata.get('url')} : {e!s}")

    return 0


if __name__ == "__main__":
    return_code = 0
    try:
        return_code = main()
    except KeyboardInterrupt:
        logger.critical("CTRL-C")
    except Exception as e:
        logger.critical("Unhandled exception")
        logger.exception(f"{e!s}", e)
        exit(254)
    finally:
        pass
    exit(return_code)
