from utils.custom_logging import get_logger
logger= get_logger("utils.performer")
from stash_ai.model import Performer, PerformerStashBox, PerformerStashBoxImage
import requests
from urllib.parse import urlparse
from PIL import Image
import io
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional, Dict, List, Union, Tuple
from stash_ai.config import config
from utils.stashbox import endpoint_to_hash
from dateutil import parser
from utils.utils import update_object_data
import json
from urllib.parse import urlparse

def get_unknown_performer_image():
    unknown_performer_img_path= config.base_dir.joinpath('assets/Unknown-performer.png')
    return Image.open(unknown_performer_img_path)

def load_performer(performer_id: int, session: Session) -> Performer:
    logger.info(f"Load performer {performer_id}")
    performer= session.get(Performer, performer_id)
    logger.debug(f"load_performer: Performer : {performer}")
    if performer is None:
        performer= create_or_update_performer_from_stash(performer_id, None, session)
    return performer

def create_or_update_performer_from_stash(performer_id: int, performer_data: Optional[Dict], session: Session) -> Performer:
    logger.info(f"Create or update performer {performer_id} from stash")    
    if performer_data is None:
        performer_data= config.stash_interface.find_performer(performer_id) if config.stash_interface is not None else None
    performer: Performer= session.get(Performer, performer_id)
    if performer is None and performer_data is None:
        return None
    url= performer_data.get('image_path')
    if url is not None:
        url= urlparse(url).path
        logger.debug(f"Parsed : {url}")    
    
    if performer is None:
        logger.info(f"Create new performer in db {performer_id}")
        performer= Performer(id= performer_data.get('id'), 
                             name=performer_data.get('name'), 
                             stash_image= url
                             )
    stash_udpated_at= parser.parse(performer_data.get('updated_at', '1970-01-01')).replace(tzinfo=None)    
    if performer.stash_updated_at is None or performer.stash_updated_at < stash_udpated_at:
        logger.info(f"Update performer {performer_id} fields with stash data")
        performer.name= performer_data.get('name')
        performer.stash_image= url
        stash_ids= []
        for stash_id in performer_data.get('stash_ids', []):
            logger.debug(f"Performer {performer_id} Stash id {stash_id}")
            stash_box_id= endpoint_to_hash(stash_id.get('endpoint'))
            for sbi in performer.stash_boxes_id:
                if sbi.stash_box_id == stash_box_id:
                    sbi.stash_id= stash_id.get('stash_id')
                    break
            else:
                sbi= PerformerStashBox(performer_id=performer_id, stash_box_id= stash_box_id, stash_id= stash_id.get('stash_id'))
                performer.stash_boxes_id.append(sbi)
                session.add(sbi)
            stash_ids.append(f"{stash_box_id}_{stash_id.get('stash_id')}")
        stash_ids_to_remove= []
        for s in performer.stash_boxes_id:
            stash_id=f"{s.stash_box_id}_{s.stash_id}"
            if stash_id not in stash_ids:
                stash_ids_to_remove.append(s)
        for s in stash_ids_to_remove:
            performer.stash_boxes_id.remove(s)
        performer.stash_updated_at= stash_udpated_at
        session.add(performer)
    return performer


def get_performer_stash_image(performer: Performer, force_download=False) -> Image.Image:
    logger.info(f"get_performer_stash_image Downloading image for performer {performer} force download {force_download}")
    if performer.stash_image is None:
        return None
    filepath= config.data_dir.joinpath(f"main_images/performer_{performer.id}.jpg")
    if filepath.exists():
        if not force_download:
            logger.debug(f"get_performer_stash_image locally served")
            return Image.open(filepath)
        else:
            logger.debug(f"get_performer_stash_image force download new image")

    if not filepath.parent.exists():
        filepath.parent.mkdir(parents=True)
        
    try:
        logger.debug(f"get_performer_stash_image download {performer.get_stash_image_url()}")
        r= requests.get(performer.get_stash_image_url(), stream=True)
        if r.status_code == 200:
            img= Image.open(io.BytesIO(r.content))
            img.save(filepath)
            return img
        else:
            logger.error(f"Unable to download {performer.stash_image}, status code {r.status_code}")
    except Exception as e:
        logger.error(f"Error downloading image {performer.stash_image} for performer {performer.id}: {e!s}")
    return None
        
def download_stash_box_images_for_performer(performer: Performer, session: Session):
    logger.info(f"Dowload images (if required) from stash box for performer {performer.name} [{performer.id}]")
    performer_images_dir= config.data_dir.joinpath(f"performer_{performer.id}")  
    logger.debug(f"Image dir : {performer_images_dir.resolve()}")
    if not performer_images_dir.exists():
        performer_images_dir.mkdir(parents=True)
    for sbi in performer.stash_boxes_id:
        sb= sbi.stash_box.get_stashboxinterface()
        sb_metadata= sb.find_performer(sbi.stash_id)
        if sb_metadata is None:
            logger.warning(f"No metadata for {sbi.stash_id} on {sbi.stash_box.name}")
        else:
            for image_metadata in sb_metadata.get('images', []):
                updated=False
                image_id= image_metadata.get('id')
                image_path= performer_images_dir.joinpath(image_id)
                image_metadata_path= performer_images_dir.joinpath(f"{image_id}.json")
                img_data= session.get(PerformerStashBoxImage, (image_id,sbi.performer_id, sbi.stash_box_id))
                if img_data is None:
                    img_data= PerformerStashBoxImage(image_id= image_id, 
                                                     performer_id= sbi.performer_id, 
                                                     stash_box_id= sbi.stash_box_id, 
                                                     url=image_metadata.get('url'),
                                                     relative_path=str(image_path.relative_to(config.data_dir)),
                                                     width= image_metadata.get('width'),
                                                     height=image_metadata.get('height')
                                                     )
                    updated= True
                else:
                    updated= update_object_data(img_data, "url", image_metadata.get('url')) or updated
                    updated= update_object_data(img_data, "width", image_metadata.get('width')) or updated
                    updated= update_object_data(img_data, "height", image_metadata.get('height')) or updated
                    updated= update_object_data(img_data, "relative_path", str(image_path.relative_to(config.data_dir))) or updated
                
                if not image_path.exists():
                    logger.info(f"Downloading {img_data.url}")
                    try:
                        response= requests.get(img_data.url)
                        updated= update_object_data(img_data, "last_status_code", response.status_code) or updated
                        if response.ok:
                            content_type= image_metadata.get('content-type')
                            updated= update_object_data(img_data, "content_type", content_type) or updated
                            with image_path.open('wb') as handler:
                                handler.write(response.content)                            
                            with image_metadata_path.open('w') as f:
                                json.dump(image_metadata, f, indent=2)
                    except Exception as e:
                        updated= update_object_data(img_data, "last_status_code", 0) or updated
                        logger.error(f"Error downloading {img_data.url} : {e!s}")
                if updated:
                    session.add(img_data)
            session.commit()

def get_downloaded_stash_box_images_for_performer(performer: Performer, session: Session, return_tuple_ids: bool= False) -> Union[List[Image.Image], Tuple[List[Image.Image], List[Tuple[str,str,str]]]]:
    logger.info(f"Loading stash box images for performer {performer.name} [{performer.id}]")
    pil_images= []
    ids=[]
    statement= select(PerformerStashBoxImage).where(PerformerStashBoxImage.performer_id == performer.id)
    img_data: PerformerStashBoxImage
    for row in session.execute(statement).fetchall():
        img_data: PerformerStashBoxImage= row[0]
        if img_data.get_image_path() is None:
            logger.warning(f"No image path for {img_data.image_id} stash box id {img_data.stash_box_id}")
            continue
        
        logger.debug(f"Image path : {img_data.get_image_path().resolve()}")
        try:
            img= Image.open(img_data.get_image_path())
            pil_images.append(img)
            ids.append((img_data.image_id, img_data.performer_id, img_data.stash_box_id))
        except Exception as e:
            logger.error(f"Error opening image at {img_data.get_image_path().resolve()} : {e!s}")        
    if return_tuple_ids:
        return (pil_images, ids)
    return pil_images