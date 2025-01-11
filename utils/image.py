from utils.custom_logging import get_logger
logger= get_logger("utils.image")
from stash_ai.model import Performer, PerformerImage
import requests
import gradio as gr
from PIL import Image
import io
import copy
def download_performer_image(url: str, performer: Performer) -> PerformerImage:
    try:
        r= requests.get(url, stream=True)
        if r.status_code == 200:
            img= Image.open(io.BytesIO(r.content))
            # pImg= copy.deepcopy(img)
            # pImg.__class__= PerformerImage
            # PerformerImage.__init__(img, performer)
            
            #img.performer= performer
            #pImg= PerformerImage(img, performer)
            return img
        else:
            logger.error(f"Unable to download {url}, status code {r.status_code}")
    except Exception as e:
        logger.error(f"Error downloading image {url} for performer {performer.id}: {e!s}")
    return None
        
    