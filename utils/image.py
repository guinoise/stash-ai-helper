from utils.custom_logging import get_logger
logger= get_logger("utils.image", True)

import gradio as gr
if gr.NO_RELOAD:
    from deepface import DeepFace
from dataclasses import dataclass, field
import pathlib
from typing import List, Union, Tuple
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import cv2
from stash_ai.model import ImageType, Img, ImgFile, ImgUri
import requests
import io
import imagehash
from stash_ai.db import get_session
from sqlalchemy.orm import Session
from sqlalchemy import select
from utils.utils import update_object_data
from stash_ai.config import config
from stash_ai.model import ImageAnalysis, DeepfaceFace, Point

def get_face_phash(face: DeepfaceFace):
    file= get_face_image_path(face)
    if file is None:
        return None
    
    im= Image.open(file)
    return imagehash.phash(im)

    
def get_face_image_path(face: DeepfaceFace):
    if face.image_analysis.image_file.mode == "RGBA":
        file= config.data_dir.joinpath(f'image_analysis/{face.image_analysis.id}/{face.id}.PNG')
    else:
        file= config.data_dir.joinpath(f'image_analysis/{face.image_analysis.id}/{face.id}.JPEG')
    if file.exists():
        return file

    if not file.parent.exists():
        file.parent.mkdir(parents=True)

    if not face.image_analysis.image_file.exists():
        logger.error(f"get_annotated_image_analysis_path Image file is missing {image_analysis.image_file}")
        return None

    source_img= Image.open(face.image_analysis.image_file.get_image_path())
    face_im= source_img.crop((face.x, face.y, face.x + face.w, face.y + face.h))
    face_im.save(file)
    return file

def get_annotated_image_analysis_path(image_analysis: ImageAnalysis, minimum_confidence: float) -> pathlib.Path:
    if image_analysis.image_file.mode == "RGBA":
        file= config.data_dir.joinpath(f'image_analysis/{image_analysis.id}_{minimum_confidence}.PNG')
    else:
        file= config.data_dir.joinpath(f'image_analysis/{image_analysis.id}_{minimum_confidence}.JPEG')
    if file.exists():
        return file
            
    if not file.parent.exists():
        file.parent.mkdir(parents=True)

    if not image_analysis.image_file.exists():
        logger.error(f"get_annotated_image_analysis_path Image file is missing {image_analysis.image_file}")
        return None

    source_img= Image.open(image_analysis.image_file.get_image_path())
    draw= ImageDraw.Draw(source_img)
    face: DeepfaceFace
    for face in image_analysis.faces:
        if face.overlapping:
            color=  (204,0,0)
        elif face.confidence < minimum_confidence:
            color=  (255,128,0)
        else:
            color=  (0,204,0)
        logger.debug(f"get_annotated_image_analysis_path {[tuple(face.get_top_left()), tuple(face.get_bottom_right())]} {source_img.size}")
        draw.rectangle([tuple(face.get_top_left()), tuple(face.get_bottom_right())], fill=None, outline=color, width=2)
        draw.text((face.x, face.y - 10), f"{face.confidence}")
    source_img.save(file)
    return file

def image_analysis(img_file: ImgFile, detector, face_expand, session: Session) -> ImageAnalysis:
    logger.info(f"image_analysis detector {detector} face_expand {face_expand} ImgFile {img_file}")
    statement= select(ImageAnalysis).where(ImageAnalysis.image_file == img_file).where(ImageAnalysis.detector==detector).where(ImageAnalysis.expand_face==face_expand)
    row= session.execute(statement).fetchone()

    if row:
        image_analysis: ImageAnalysis= row[0]
        logger.info(f"image_analysis : Analysis already done, returning db results")
        return image_analysis

    if not img_file.exists():
        logger.error(f"image_analysis Img file not on disk {img_file}")    
        return None
    
    image_analysis: ImageAnalysis= ImageAnalysis(image_file= img_file, detector=detector, expand_face=face_expand)
    session.add(image_analysis)

    try:
        results= DeepFace.analyze(img_file.get_image_path(), detector_backend=detector, actions=["age", "gender", "race"], enforce_detection=True, expand_percentage=face_expand)
        for face_result in results:
            face= DeepfaceFace(image_analysis=image_analysis,
                               x=face_result["region"]["x"],
                               y= face_result["region"]["y"],
                               w= face_result["region"]["w"],
                               h= face_result["region"]["h"],
                               age= face_result["age"],
                               gender= face_result["dominant_gender"],
                               gender_confidence=face_result["gender"][face_result["dominant_gender"]],
                               race=face_result["dominant_race"],
                               race_confidence=face_result["race"][face_result["dominant_race"]],
                               confidence=face_result["face_confidence"]
                               )
            other_face: DeepfaceFace
            for other_face in image_analysis.faces:
                if face.overlap(other_face):
                    other_face.overlapping= True
                    face.overlapping= True
            image_analysis.faces.append(face)
            session.add(face)
    except ValueError:
        logger.info(f"image_analysis Image {image_analysis} has no face(s)")
    session.commit()
    return image_analysis
        
        
def hashes_are_similar(left_hash, right_hash, tolerance=6):
    """
    Return True if the hamming distance between
    the image hashes are less than the given tolerance.
    """
    return (left_hash - right_hash) <= tolerance    
    
def convert_rgba_to_rgb(img: Image.Image, background_color= (0,0,0)) -> Image.Image:
    logger.debug("convert_rgba_to_rgb")
    background= Image.new("RGB", img.size, background_color)
    background.paste(img, mask=img.split()[3]) #3 is the alpha channel
    return background
    
def download_image(uri: str, img_type: ImageType, save_base_name: str, current_session: Session) -> Tuple[ImgFile, Image.Image]:
    logger.info(f"download_image Downloading image at {uri}")        
    try:
        if current_session is None:
            session= get_session()
        else:
            session= current_session       
        if uri.startswith('stash://'):
            download_uri= f"{config.stash_base_url}{uri[8:]}"
        else:
            download_uri= uri
        r= requests.get(download_uri, stream=True)
        if r.ok:
            pImg= Image.open(io.BytesIO(r.content))
            content_type= r.headers['content-type']
            phash= str(imagehash.phash(pImg))
            external_uri= session.get(ImgUri, uri)
            if external_uri is not None:
                img= external_uri.img
            else:
                img= session.get(Img, phash)
            updated= False
            if img is None:
                logger.debug("New img object")
                img= Img(phash= phash, image_type= img_type)
                img.external_uris.append(ImgUri(uri=uri, img=img))
                updated= True
            else:
                for external_uri in img.external_uris:
                    if external_uri.uri == uri:
                        break
                else:
                    img.external_uris.append(ImgUri(uri=uri, img=img))
                    updated= True
                # if update_object_data(img, 'image_type', img_type):
                #     logger.warning("Image type changed for image")
                #     updated= True                    
            if updated:
                session.add(img)
            updated= False
            w, h= pImg.size
            scale= max(w,h)
            imgFile: ImgFile
            overwrite_image= False
            for imgFile in img.files:
                if imgFile.scale == scale:
                    if update_object_data(imgFile, 'content_type', content_type):
                        logger.warning("New content type for image, overwrite")
                        updated= True
                        overwrite_image= True
                    if update_object_data(imgFile, 'width', w) or update_object_data(imgFile, 'height', h):
                        logger.warning("New resolution for image, overwrite")
                        updated= True
                        overwrite_image= True
                    if update_object_data(imgFile, 'mode', pImg.mode):
                        logger.warning("New image mode")
                        updated= True
                        overwrite_image= True
                    if update_object_data(imgFile, 'format', pImg.format):
                        logger.warning("New image format")
                        updated= True
                        overwrite_image= True
                    if update_object_data(img, 'original_scale', scale):
                        img.original= imgFile
                        session.add(img)
                    break
            else:
                logger.debug("New image file")
                relative_path= f"{save_base_name}.{pImg.format}"
                imgFile= ImgFile(img= img, scale=scale, mode=pImg.mode,format=pImg.format, content_type= content_type, width=w, height=h, relative_path= relative_path)
                img.files.append(imgFile)
                img.original_scale= scale
                updated= True
            if not imgFile.exists():
                if not imgFile.get_image_path().parent.exists():
                    imgFile.get_image_path().parent.mkdir(parents=True)
                pImg.save(imgFile.get_image_path(), format=pImg.format)
            if overwrite_image and imgFile.relative_path:
                logger.warning("Overwritting image")
                if not imgFile.get_image_path().parent.exists():
                    imgFile.get_image_path().parent.mkdir(parents=True)
                pImg.save(imgFile.get_image_path(), format=pImg.format)
            if updated:
                session.add(imgFile)
            return (imgFile, pImg)
        else:
            logger.error(f"download_image Unable to download {uri}, status code {r.status_code}")
    except Exception as e:
        logger.error(f"download_image Error downloading image {uri}: {e!s}")
        logger.exception(e)
    finally:
        if current_session is None:
            session.commit() 
    return (None, None)
    