from utils.custom_logging import get_logger
logger= get_logger("utils.image")
from stash_ai.db import get_session
from stash_ai.model import StashBox
import hashlib
from stash_ai.config import config

def endpoint_to_hash(endpoint: str) -> str:
    hash= hashlib.md5()
    hash.update(endpoint.encode())
    return hash.hexdigest()

def init_stashboxes():
    stash_boxes= config.stash_configuration.get('general', {}).get('stashBoxes', []) if config.stash_configuration is not None else None
    boxes= []
    with get_session(expire_on_commit=False) as session:
        logger.info("Update stash boxes in database")
        for stash_box in stash_boxes:
            if not stash_box.get('endpoint'):
                continue
            id= endpoint_to_hash(stash_box.get('endpoint'))
            sb: StashBox= session.get(StashBox, id)
            if sb is None:
                sb= StashBox(id= id, endpoint= stash_box.get('endpoint'), name=stash_box.get('name'), api_key=stash_box.get('api_key'))
            else:
                sb.name= stash_box.get('name')
                sb.api_key= stash_box.get('api_key')
            session.add(sb)
            logger.info(f"Loaded {sb!s}")
            boxes.append(sb)
        session.commit()
    config.stash_boxes= boxes