from Objects import Performer
import json
import pathlib
from custom_logger import root_logger
logger= root_logger.getChild("Utils")


def save_performer(performer: Performer) -> bool:
    if performer.metadata_file is None:
        logger.error(f"Metadata file is not setted for performer {performer.id}, cannot save.")
        return False
    if performer.metadata is None:
        logger.error(f"Metadata is not setted for performer {performer.id}, cannot save.")
        return False

    try:
        if 'obj_metadata' not in performer.metadata.keys():
            performer.metadata['obj_metadata']= {}
        performer.metadata['obj_metadata']['safe_name']= performer.safe_name
        performer.metadata['obj_metadata']['stash_box']= performer.stash_box
        performer.metadata['obj_metadata']['id']= performer.id
        performer.metadata['obj_metadata']['metadata_filename']= performer.metadata_file.name
        performer.metadata['obj_metadata']['stash_box_images_dir']= str(performer.stash_box_images_dir.relative_to(performer.metadata_file.parent))
        with performer.metadata_file.open('w') as fp:
            json.dump(performer.metadata, fp, indent=2)
        logger.info(f"Performer {performer.safe_name} saved into {performer.metadata_file.name}")
        return True
    except Exception as e:
        logger.error(f"Error saving performer {performer.id} into {performer.metadata_file.resolve()} : {e!s}")
        return False

def load_metadata_file_for_performer(performer: Performer) -> bool:
    performer.download_metadata= True
    if performer.metadata_file.exists():
        try:
            with performer.metadata_file.open('r') as f:
                performer.metadata= json.load(f)
            performer.download_metadata= False
            return True
        except Exception as e:
            logger.error(f"Unable to load metada file {performer.metadata_file.name}. Will download from stashbox. Error : {e!s}")
            return False
    return False

def load_performer_from_metadata_file(file: pathlib.Path) -> Performer:
    try:
        with file.open('r') as f:
            data= json.load(f)
        obj_metadata= data.get('obj_metadata', {})
        return Performer(id= obj_metadata.get('id'),
                  stash_box= obj_metadata.get('stash_box'),
                  safe_name= obj_metadata.get('safe_name'),
                  metadata_file=file,
                  stash_box_images_dir= file.parent.joinpath(obj_metadata.get('stash_box_images_dir')),
                  download_metadata=False
                  )
    except Exception as e:
        logger.error(f"Unable to load metada file {file.resolve()}. Error : {e!s}")
        return None