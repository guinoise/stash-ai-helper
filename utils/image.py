from utils.custom_logging import get_logger
logger= get_logger("utils.image")

import gradio as gr
if gr.NO_RELOAD:
    from deepface import DeepFace
from dataclasses import dataclass, field
import pathlib
from typing import List, Union, Tuple
import numpy as np
from PIL import Image
import cv2
from stash_ai.model import ImageType, Img, ImgFile, ImgUri
import requests
import io
import imagehash
from stash_ai.db import get_session
from sqlalchemy.orm import Session
from utils.utils import update_object_data
from stash_ai.config import config

@dataclass
class Point():
    x: int
    y: int
    
    def __iter__(self):
        yield self.x
        yield self.y

@dataclass
class Face():
    x: int
    y: int
    w: int
    h: int
    age: int= None
    gender: str= None
    gender_confidence: float= None
    race: str= None
    race_confidence: float= None
    confidence: float= 0
    overlapping: bool= False

    def get_top_left(self):
        return Point(self.x, self.y)
    
    def get_top_right(self):
        return Point(self.x + self.w, self.y)
    
    def get_bottom_left(self):
        return Point(self.x, self.y + self.h)
    
    def get_bottom_right(self):
        return Point(self.x + self.w, self.y + self.h)
    
    def overlap(self, other) -> bool:
        return not (self.get_top_right().x < other.get_bottom_left().x
                    or self.get_bottom_left().x > other.get_top_right().x
                    or self.get_top_right().y < other.get_bottom_left().y
                    or self.get_bottom_left().y > other.get_top_right().y)
    
    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (X: {self.x} Y: {self.y} W: {self.w} H: {self.h} Age: {self.age} Gender: {self.gender} {self.gender_confidence} Race: {self.race} ({self.race_confidence}))"

@dataclass
class ImageAnalysis():
    file: pathlib.Path= None
    name: str= None
    sample: bool= False
    faces: List= field(default_factory=lambda: [])
    pil= None
    np_array= None
        
    def get_pil_image(self):
        if self.pil is not None:
            return self.pil
        if self.np_array is not None:
            return Image.fromarray(self.np_array)
        return Image.open(self.file)
            
    def get_numpy(self):
        if self.np_array is not None:
            return self.np_array
        elif self.pil is not None:
            return np.array(self.pil)
        
        return np.asarray(self.get_pil_image())
        
    def get_numpy_with_overlay(self, face_min_confidence: float= 0):
        img= np.copy(self.get_numpy())
        face: Face
        for face in self.faces:
            if face.overlapping:
                color=  (204,0,0)
            elif face.confidence < face_min_confidence:
                color=  (255,128,0)
            else:
                color=  (0,204,0)
            logger.debug(f"get_numpy_with_overlay face {face} color {color}")
            img= cv2.rectangle(img, tuple(face.get_top_left()), tuple(face.get_bottom_right()), color, 3)
            cv2.putText(img, f"{face.confidence}", (face.x, face.y - 10),  cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)
        return img

    def get_faces_pil(self, face_min_confidence: float= 0) -> List[Tuple[Face, Image.Image]]:
        im= self.get_pil_image()
        ims: List[Image.Image]= []
        face: Face
        for face in self.faces:
            if face.confidence < face_min_confidence:
                continue
            ims.append((face, im.crop((face.get_top_left().x, face.get_top_left().y, face.get_bottom_right().x, face.get_bottom_right().y))))
        return ims
        
    def get_faces_numpy(self, face_min_confidence: float= 0) -> List[Tuple[Face, np.ndarray]]:
        im= self.get_numpy()
        ims: List[np.ndarray]= []
        face: Face
        for face in self.faces:
            if face.confidence < face_min_confidence:
                continue
            ims.append((face, im[face.y:face.y+face.h, face.x:face.x+face.w]))
        return ims

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Name: {self.name} Sample: {self.sample} Faces: {self.faces} Path: {self.file}))"
          
def image_analysis(image: Union[Image.Image, np.ndarray, pathlib.Path, str], detector, face_expand) -> ImageAnalysis:
    logger.info(f"image_analysis type {type(image)} detector {detector} face_expand {face_expand}")
    imAnalysis= ImageAnalysis()
    if isinstance(image, Image.Image):
        imAnalysis.pil= image
    elif isinstance(image, np.ndarray):
        imAnalysis.np_array= image
    elif isinstance(image, pathlib.Path):
        imAnalysis.file= image
        imAnalysis.name= image.stem
    else:
        imAnalysis.file= pathlib.Path(image)
        imAnalysis.name= imAnalysis.file.stem
    
    try:
        results= DeepFace.analyze(imAnalysis.get_numpy(), detector_backend=detector, actions=["age", "gender", "race"], enforce_detection=True, expand_percentage=face_expand)
        for face_result in results:
            face= Face(x=face_result["region"]["x"],
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
            other_face: Face
            for other_face in imAnalysis.faces:
                if face.overlap(other_face):
                    other_face.overlapping= True
                    face.overlapping= True
            imAnalysis.faces.append(face)
    except ValueError:
        logger.info(f"image_analysis Image {imAnalysis} has no face(s)")
    return imAnalysis
        
        
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
    