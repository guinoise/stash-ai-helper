#import stashapi.log as log
from stashapi.stashapp import StashInterface
from custom_logger import logger
import logging
from datetime import datetime
import pathlib
import json
import argparse as ap

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
    parser.add_argument('--scene-id', '-s', type=int, action='store', required=True)
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)
    # else:
    #     logging.getLogger("StashLogger").setLevel(logging.WARNING)
    if args.warning:
        logger.setLevel(logging.WARNING)

    base_dir = pathlib.Path(__file__).parent.resolve()

    stash = StashInterface({
        "scheme": "http",
        "host":"localhost",
        "port": "9999",
        "logger": logger
    })
    
    scene_data= stash.find_scene(args.scene_id)
    if scene_data is None:
        logger.warning(f"Scene {args.id} not found")
    else:
        filename= scene_data.get('files', [{}])[0].get('basename')
        phash=None
        for fingerprint in scene_data.get('files', [{}])[0].get('fingerprints', [{}]):
            if fingerprint.get('type') == 'phash':
                phash= fingerprint.get('value')
                break
        logger.info(f"Id {scene_data.get('id')} {filename} phash: {phash}")    
        out_file= base_dir.joinpath(f"scene_{scene_data.get('id')}.json")
        with out_file.open('w') as fp:
            json.dump(scene_data, fp, indent=2)
        logger.info(f"Scene data saved to : {out_file.name}")
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
