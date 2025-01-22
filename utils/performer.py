from utils.custom_logging import get_logger
logger= get_logger("utils.performer")
from stash_ai.model import Performer, PerformerStashBox, PerformerStashBoxImage, ImageType, ImgFile, Img, ImgUri
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
from stash_ai.db import get_session
from tqdm import tqdm
import gradio as gr
from utils.image import convert_rgba_to_rgb, download_image
import imagehash

def download_all_stash_images(current_session: Session= None, progress=gr.Progress(track_tqdm=True)):
    logger.info(f"download_all_stash_images")
    if current_session is None:
        session= get_session()
    else:
        session= current_session
        
    statement= select(Performer)
    for row in tqdm(session.execute(statement).fetchall(), desc="Downloading...", unit='performer'):
        performer: Performer= row[0]
        logger.debug(f"download_all_stash_images {performer}")
        download_stash_box_images_for_performer(performer, session)
        

    if current_session is None:
        session.commit()

def sync_all_performers(current_session: Session= None, progress=gr.Progress(track_tqdm=True)):
    logger.info(f"sync_all_performers")
    if current_session is None:
        session= get_session()
    else:
        session= current_session

    ids= []    
    for stash_performer in config.stash_interface.find_performers():
        ids.append(stash_performer.get('id'))
        
    for id in tqdm(ids, desc='Updating', unit='performer'):
        create_or_update_performer_from_stash(id, None, session)
    
    if current_session is None:
        session.commit()
    
def update_all_performers(current_session: Session= None, progress=gr.Progress(track_tqdm=True)):
    logger.info(f"update_all_performers")
    if current_session is None:
        session= get_session()
    else:
        session= current_session
        
    statement= select(Performer)
    ids= []
    for row in session.execute(statement).fetchall():
        performer: Performer= row[0]
        ids.append(performer.id)
    
    for id in tqdm(ids, desc='Updating', unit='performer'):
        create_or_update_performer_from_stash(id, None, session)
    
    if current_session is None:
        session.commit()


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
        get_performer_stash_image(performer, force_download=True, session=session)
        session.add(performer)
    return performer


def get_performer_stash_image(performer: Performer, force_download=False, session: Session= None) -> Image.Image:
    logger.info(f"get_performer_stash_image Downloading image for performer {performer} force download {force_download}")
    if performer.stash_image is None:
        return None
    current_session= session if session is not None else get_session()
    logger.debug(f"get_performer_stash_image session : {session}")    
    try:
        if performer.main_image:
            img: Img= performer.main_image
            logger.debug(f"get_performer_stash_image img: {img}")
            imgFile= img.original_file()
            logger.debug(f"get_performer_stash_image imgFile: {imgFile}")
            if not force_download and imgFile and imgFile.exists():
                logger.debug(f"get_performer_stash_image locally served")
                return Image.open(imgFile.get_image_path())
            elif imgFile:
                logger.debug(f"get_performer_stash_image force download new image")        
        
        logger.debug(f"get_performer_stash_image download {performer.stash_image}")

        imgFile: ImgFile
        img: Image.Image
        imgFile, img= download_image(f"stash://{performer.stash_image}", ImageType.PERFORMER_MAIN, f"main_images/performer_{performer.id}", current_session)
        if performer not in imgFile.img.performers:
            imgFile.img.performers.append(performer)
            performer.main_image= imgFile.img
            current_session.add(imgFile.img)
            current_session.add(performer)
        return img
    except Exception as e:
        logger.error(f"get_performer_stash_image Error downloading image {performer.stash_image} for performer {performer.id}: {e!s}")
        logger.exception(e)
    finally:
        if session is None:
            current_session.commit()
    return None
        
def download_stash_box_images_for_performer(performer: Performer, session: Session):
    logger.info(f"Dowload images (if required) from stash box for performer {performer.name} [{performer.id}]")
    performer_images_dir= config.data_dir.joinpath(f"performer_{performer.id}")  
    logger.debug(f"Image dir : {performer_images_dir.resolve()}")
    if not performer_images_dir.exists():
        performer_images_dir.mkdir(parents=True)
    for sbi in performer.stash_boxes_id:
        try:
            sb= sbi.stash_box.get_stashboxinterface()
            sb_metadata= sb.find_performer(sbi.stash_id)
        except Exception as e:
            logger.error(f"Error getting performer {sbi.stash_id} from stashbox {sbi.stash_box.name} : {e!s}")
            sb_metadata= None
        if sb_metadata is None:
            logger.warning(f"No metadata for {sbi.stash_id} on {sbi.stash_box.name}")
        else:
            for image_metadata in sb_metadata.get('images', []):
                image_id= image_metadata.get('id')
                image_path= performer_images_dir.joinpath(image_id)
                imgUri= session.get(ImgUri, image_metadata.get('url'))
                if imgUri:
                    img= imgUri.img
                    if update_object_data(img, 'image_type', ImageType.STASH_BOX_PERFORMER):
                        session.add(img)
                    if performer not in img.performers:
                        img.performers.append(performer)
                        session.add(img)
                    if img.original_file_exists():
                        continue
                (imgFile, im)= download_image(image_metadata.get('url'), ImageType.STASH_BOX_PERFORMER, str(image_path.relative_to(config.data_dir)), session)
                imgFile.img.performers.append(performer)
                session.add(imgFile)
            session.commit()

def get_downloaded_stash_box_images_for_performer(performer: Performer, session: Session, return_tuple_ids: bool= False) -> Union[List[Image.Image], Tuple[List[Image.Image], List[Tuple[str,str,str]]]]:
    logger.info(f"Loading stash box images for performer {performer.name} [{performer.id}]")
    pil_images= []
    ids=[]
    img: Img
    for img in performer.images:
        if img.image_type == ImageType.STASH_BOX_PERFORMER or img.phash == performer.main_image_phash:
            if not img.original_file_exists():
                logger.warning(f"Image not on disk {img.phash}")
                continue
            img_file= img.original_file()
            im= Image.open(img_file.get_image_path())
            ids.append(img_file.id)
            pil_images.append(im)        
    if return_tuple_ids:
        return (pil_images, ids)
    return pil_images