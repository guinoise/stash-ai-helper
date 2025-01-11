from utils.custom_logging import get_logger
logger= get_logger("utils.image")
from stash_ai.model import Performer
import requests
from PIL import Image
import io
from sqlalchemy.orm import Session

def load_performer(performer_id: int, session: Session) -> Performer:
    logger.info(f"Load performer {performer_id}")
    return session.get(Performer, performer_id)

def get_performer_from_performer_data(performer_data: dict, session: Session, create: bool= True) -> Performer:
    logger.info(f"Retreive performer {performer_data.get('id')} from database (create if not exists)")    
    performer: Performer= session.get(Performer, performer_data.get('id'))
    if performer is None and create:
        performer= Performer(id= performer_data.get('id'), name=performer_data.get('name'), stash_image= performer_data.get('image_path'))
        session.add(performer)
    return performer


def download_performer_image_from_performer_data(performer: Performer) -> Image.Image:
    logger.info(f"Downloading image for performer {performer}")
    try:
        r= requests.get(performer.stash_image, stream=True)
        if r.status_code == 200:
            img= Image.open(io.BytesIO(r.content))
            return img
        else:
            logger.error(f"Unable to download {performer.stash_image}, status code {r.status_code}")
    except Exception as e:
        logger.error(f"Error downloading image {performer.stash_image} for performer {performer.id}: {e!s}")
    return None
        
    