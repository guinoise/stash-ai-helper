from utils.custom_logging import get_logger
logger= get_logger("utils.scene")

import gradio as gr
from stash_ai.config import config
import math
import cv2
import shutil
from dataclasses import dataclass, field
import pathlib
from typing import List
import numpy as np
from PIL import Image
from matplotlib import colors

if gr.NO_RELOAD:
    from deepface import DeepFace

@dataclass
class Point():
    x: int
    y: int
    
    def to_tuple(self):
        return (self.x, self.y)

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
    file: pathlib.Path
    name: str
    sample: bool= False
    faces: List= field(default_factory=lambda: [])
    
    def get_pil_image(self):
        return Image.open(self.file)
            
    def get_numpy(self):
        return np.asarray(self.get_pil_image())
        
    def get_numpy_with_overlay(self, face_min_confidence: float= 0):
        img= np.copy(self.get_numpy())
        face: Face
        for face in self.faces:
            if face.overlapping:
                color=  colors.hex2color(colors.cnames['red'])
            elif face.confidence < face_min_confidence:
                color=  colors.hex2color(colors.cnames['yellow'])
            else:
                color=  colors.hex2color(colors.cnames['green'])
            img= cv2.rectangle(img, face.get_top_left().to_tuple(), face.get_bottom_right().to_tuple(), color, 3)
            cv2.putText(img, f"{face.confidence}", (face.x, face.y - 10),  cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 3)
        return img
    
    def get_faces_numpy(self, face_min_confidence: float= 0) -> List[np.ndarray]:
        im= self.get_numpy()
        ims: List[np.ndarray]= []
        face: Face
        for face in self.faces:
            if face.confidence < face_min_confidence:
                continue
            ims.append(im[face.y:face.get_top_right().y, face.x:face.get_bottom_right().x])
        return ims

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Name: {self.name} Sample: {self.sample} Faces: {self.faces} Path: {self.file}))"
    
#outputs=[gallery_face_dection, gallery_sample_faces, gallery_unique_faces]
def extract_video_images(video, video_duration: float, fps: float, extract_n_images_per_seconds: float, number_of_samples, progress= None):
    nb_images= math.ceil(video_duration * extract_n_images_per_seconds)
    logger.info(f"extract_images URL: {video} Img per second : {extract_n_images_per_seconds} FPS: {fps} Total images: {nb_images} Samples: {number_of_samples}")
    images= []
    every_n_frames= round(fps / extract_n_images_per_seconds)
    sample_every_n_images= math.floor(nb_images / number_of_samples)
    nb_frames= math.floor(video_duration*fps)
    logger.info(f"extract_images Extracte every {every_n_frames} frames. Total of frames {nb_frames}")
    if progress is not None:
        progress(0, desc="Extracting...", total=nb_frames, unit="frame")
    extract_directory= config.data_dir.joinpath('scene_extraction').joinpath('extracted_images')
    if extract_directory.exists():
        shutil.rmtree(extract_directory)
    extract_directory.mkdir(parents=True)
    
    if video is None:
        gr.Warning("Url is empty, could not extract.")
    else:
        nb_extracted= 0
        try:
            logger.debug(f"extract_images Open VideoCapture {video}")
            cap= cv2.VideoCapture(video)
            frame= 0
            success= True
            while success:
                success, image= cap.read()
                if (frame % every_n_frames) == 0:
                    if nb_extracted % sample_every_n_images == 0 and len(images) < number_of_samples:
                        image_path= extract_directory.joinpath(f"{nb_extracted:010}_sample.jpg")
                        images.append(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                        logger.debug(f"Image {nb_extracted} / {nb_images} extracted to {image_path.name}")
                    else:
                        image_path= extract_directory.joinpath(f"{nb_extracted:010}.jpg")
                    cv2.imwrite(image_path, image)
                    nb_extracted+= 1
                    #logger.debug(f"Image {nb_extracted} / {nb_images} extracted to {image_path.name}")
                frame+= 1
                if progress is not None:
                    progress(frame/nb_frames)
        except Exception as e:
            logger.error(f"extract_images Error extraction {video} : {e!s}")
        logger.info(f"extract_images Extracted {nb_extracted} / {nb_images}")
        if nb_extracted < nb_images - 1:
            gr.Warning(f"Extracted only {nb_extracted} over {nb_images}")
    return images

def analyse_extracted_video(detector, face_expand, dryrun, progress= None) -> List[ImageAnalysis]:
    logger.info(f"analyse_extracted_video Detector: {detector} Extends: {face_expand}%")
    if dryrun:
        logger.warning(f"analyse_extracted_video DRY RUN, Proceding only on samples")
    extract_directory= config.data_dir.joinpath('scene_extraction').joinpath('extracted_images')
    if not extract_directory.exists():
        gr.Warning("No data extracted, cannot process")
        return [None, None, None]
    
    images_metadata: List[ImageAnalysis]= []
    for f in extract_directory.iterdir():
        if not f.is_file():
            continue
        img_metadata= ImageAnalysis(f, f.stem, f.stem.endswith('_sample'))
        if dryrun and not img_metadata.sample:
            logger.debug(f"analyse_extracted_video dry run skip {img_metadata.name}")
            continue
        images_metadata.append(img_metadata)
    
    total_count= len(images_metadata)
    logger.info(f"analyse_extracted_video {total_count} image(s) to analyze")
    if progress is not None:
        progress(0, desc="Analyzing...", total=total_count, unit="image")
        
    for index, metadata in enumerate(images_metadata):
        if progress is not None:
            progress(index/total_count)
        
        try:
            results= DeepFace.analyze(metadata.get_numpy(), actions=["age", "gender", "race"], enforce_detection=True, expand_percentage=face_expand)
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
                for other_face in metadata.faces:
                    if face.overlap(other_face):
                        other_face.overlapping= True
                        face.overlapping= True
                metadata.faces.append(face)
            logger.debug(f"analyse_extracted_video Analyzed {metadata}")
        except ValueError:
            logger.info(f"analyse_extracted_video Image {metadata} has no face(s)")
    return images_metadata