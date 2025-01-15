from utils.custom_logging import get_logger
logger= get_logger("utils.scene")

import gradio as gr
from stash_ai.config import config
from stash_ai.db import get_session
import math
import cv2
import shutil
from typing import List, Optional, Dict
from stash_ai.model import Scene, Performer
from utils.image import ImageAnalysis, image_analysis, hashes_are_similar
from sqlalchemy.orm import Session
from dateutil import parser
from datetime import datetime
from utils.utils import update_object_data
from utils.performer import load_performer, get_performer_stash_image
from urllib.parse import urlparse
import pathlib
import imagehash
from PIL import Image
from tqdm import tqdm
import decord as de

def create_or_update_scene_from_stash(scene_id: int, scene_json: Optional[Dict], session: Session) -> Scene:
    logger.info(f"create_or_update_scene_from_stash {scene_id} from stash")    
    if scene_json is None:
        scene_json= config.stash_interface.find_scene(scene_id) if config.stash_interface is not None else None
    scene: Scene= session.get(Scene, scene_id)
    if scene_json is None:
        gr.Warning("Could not retrieve data from stash")
        return scene
    url= scene_json.get('sceneStreams', [{}])[0].get('url')
    logger.debug(f"create_or_update_scene_from_stash {scene_id} url {url}")
    if url is not None:
        url= urlparse(url).path
        logger.debug(f"Parsed : {url}")
    if scene is None and scene_json is None:
        return None
    if scene is None:
        logger.info(f"create_or_update_scene_from_stash Create new scene in db {scene_id}")
        scene: Scene = Scene(id= scene_json.get('id'),
                             url= url,
                             local_file_name= scene_json.get('files', [{}])[0].get('path'),
                             video_codec= scene_json.get('files', [{}])[0].get('video_codec'),
                             width= scene_json.get('files', [{}])[0].get('width'),
                             height= scene_json.get('files', [{}])[0].get('height'),
                             fps= scene_json.get('fps', [{}])[0].get('frame_rate'),
                             duration= scene_json.get('duration', [{}])[0].get('duration'),
                             relative_extract_dir= str(config.data_dir.joinpath('scene_extraction').joinpath(f"extracted_scene_{scene_id}").relative_to(config.data_dir.joinpath('scene_extraction'))),
                             relative_downscale_extract_dir= str(config.data_dir.joinpath('scene_extraction').joinpath(f"extracted_scene_{scene_id}_downscale").relative_to(config.data_dir.joinpath('scene_extraction'))),
                             relative_extract_face_dir= str(config.data_dir.joinpath('scene_extraction').joinpath(f"extracted_scene_{scene_id}_faces").relative_to(config.data_dir.joinpath('scene_extraction'))),
                             relative_downscale_extract_face_dir= str(config.data_dir.joinpath('scene_extraction').joinpath(f"extracted_scene_{scene_id}_faces_downscale").relative_to(config.data_dir.joinpath('scene_extraction')))
                      )
        
        
    stash_udpated_at= parser.parse(scene_json.get('updated_at', '1970-01-01')).replace(tzinfo=None)    
    if scene.stash_updated_at is None or scene.stash_updated_at < stash_udpated_at:
        logger.info(f"create_or_update_scene_from_stash Update scene {scene_id} fields with stash data")
        update_object_data(scene, 'title', scene_json.get('title'))
        update_object_data(scene, 'details', scene_json.get('details'))
        update_object_data(scene, 'url', url)
        update_object_data(scene, 'local_file_name', scene_json.get('files', [{}])[0].get('path'))
        update_object_data(scene, 'video_codec', scene_json.get('files', [{}])[0].get('video_codec'))
        update_object_data(scene, 'width', scene_json.get('files', [{}])[0].get('width'))
        update_object_data(scene, 'height', scene_json.get('files', [{}])[0].get('height'))
        update_object_data(scene, 'fps', scene_json.get('files', [{}])[0].get('frame_rate'))
        update_object_data(scene, 'duration', scene_json.get('files', [{}])[0].get('duration'))
        performers_ids= []
        
        for performer_json in scene_json.get('performers', []):
            performer: Performer= load_performer(performer_json.get('id'), session)
            scene.performers.append(performer)
            performers_ids.append(performer.id)
            session.add(performer)
        
        performers_to_remove= []
        performer: Performer
        for performer in scene.performers:
            if performer.id not in performers_ids:
                logger.warning(f"create_or_update_scene_from_stash Removing performer {performer.id} from scene")
                performers_to_remove.append(performer)
        for performer in performers_to_remove:
            scene.performers.remove(performer)
        logger.debug(f"create_or_update_scene_from_stash performers before exit {scene.performers}")
        scene.stash_updated_at= stash_udpated_at
        #Force download of image
        get_performer_stash_image(performer, True)
        session.add(scene)
    return scene


def load_scene(scene_id: int, session: Session) -> Scene:
    logger.info(f"load_scene {scene_id}")
    scene= session.get(Scene, scene_id)
    logger.debug(f"load_scene: Scene : {scene}")
    if scene is None:
        scene= create_or_update_scene_from_stash(scene_id, None, session)
    return scene    

def decord_scene(scene: Scene,hash_tolerance: int= 20, downscale: int= 512, session: Session= None) -> bool:
    image_hashes= []
    nb_frames= scene.number_of_frames()
    logger.info(f"extract_images Scene: {scene.id} FPS: {scene.fps} Hash tolerance {hash_tolerance} Total frames: {nb_frames}")
    logger.debug(f"extract_images Scene: {scene}")

    if session is None:
        logger.info(f"extract_images : Opening a session to the DB")
        local_session= get_session()
    else:
        local_session= session

    location= None 
    start= None   
    try:
        extract_directory= scene.get_extract_dir()
        extract_directory_downscale= scene.get_downscale_extract_dir()

        for d in [extract_directory, extract_directory_downscale]:
            if d is None:
                logger.warning("At least one directory is not setted")
                raise gr.Error("At least one extraction directory is not setted. Unable to extract.")
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
        
        scene.nb_images= 0
        scene.nb_faces= 0
        scene.downscale= downscale
        scene.downscale_width= 0
        scene.downscale_height= 0
        scene.hash_tolerance= hash_tolerance
        
        if scene.local_file_name is not None:
            local_file= pathlib.Path(scene.local_file_name)
            if local_file.is_file():
                location= local_file
        if location is None and scene.url is not None:
            location= scene.get_url()
            
        
        if location is None:
            gr.Warning("Unable to locate the video, could not extract.")
        else:
            
            logger.debug(f"extract_images Open VideoCapture {location}")
            ctx= de.cpu()
            videos= [location]
            vl= de.VideoLoader(videos, ctx, (6, scene.height, scene.width, 3), 1,1,1)
            frame= 0
            for batch in tqdm(vl, desc="Extracting...", unit="frame"):
                for bb in batch:
                    image= bb.asnumpy()
                    pImg= Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                    phash= imagehash.phash(pImg)
                    frame+= 1
                    if frame % 500 == 0:
                        logger.debug(f"Image {scene.nb_images} frame {frame} of {nb_frames}")
                    for other_hash in image_hashes:
                        if hashes_are_similar(other_hash, phash):
                            break
                    else:
                        image_name= f"{phash}.jpg"
                        image_path= extract_directory.joinpath(image_name)
                        pImg.save(image_path)
                        pImg.thumbnail((downscale, downscale))
                        image_path= extract_directory_downscale.joinpath(image_name)
                        pImg.save(image_path)
                        scene.nb_images+= 1
                        image_hashes.append(phash)
                        if scene.nb_images == 1:
                            scene.downscale_width, scene.downscale_height= pImg.size
    except Exception as e:
        logger.error(f"extract_images Error extraction {location} : {e!s}")
        logger.exception(e)
    finally:
        if start is None:
            scene.extraction_time= None
        else:
            duration= (datetime.now() - start)
            scene.extraction_time = duration.total_seconds()
            logger.info(f"extract_images Extraction time : {duration}")
        if session is None:
            local_session.commit()
    logger.info(f"extract_images Extracted {scene.nb_images} over {nb_frames} frames")
    return True
    

def extract_scene_images(scene: Scene,hash_tolerance: int= 20, downscale: int= 512, session: Session= None) -> bool:
    image_hashes= []
    nb_frames= scene.number_of_frames()
    logger.info(f"extract_images Scene: {scene.id} FPS: {scene.fps} Hash tolerance {hash_tolerance} Total frames: {nb_frames}")
    logger.debug(f"extract_images Scene: {scene}")

    if session is None:
        logger.info(f"extract_images : Opening a session to the DB")
        local_session= get_session()
    else:
        local_session= session

    location= None 
    start= None   
    try:
        progress= tqdm(desc="Extracting...", total=nb_frames, unit="frame")

        extract_directory= scene.get_extract_dir()
        extract_directory_downscale= scene.get_downscale_extract_dir()
        
        for d in [extract_directory, extract_directory_downscale]:
            if d is None:
                logger.warning("At least one directory is not setted")
                raise gr.Error("At least one extraction directory is not setted. Unable to extract.")
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True)
        
        scene.nb_images= 0
        scene.nb_faces= 0
        scene.downscale= downscale
        scene.downscale_width= 0
        scene.downscale_height= 0
        scene.hash_tolerance= hash_tolerance
        
        if scene.local_file_name is not None:
            local_file= pathlib.Path(scene.local_file_name)
            if local_file.is_file():
                location= local_file
        if location is None and scene.url is not None:
            location= scene.get_url()
            
        
        if location is None:
            gr.Warning("Unable to locate the video, could not extract.")
        else:
            logger.debug(f"extract_images Open VideoCapture {location}")
            cap= cv2.VideoCapture(location)
            frame= 0
            success= True
            start= datetime.now()
            while success:
                success, image= cap.read()
                if frame == 0: 
                    logger.debug(f"*** {success} ")
                if success:
                    pImg= Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                    phash= imagehash.phash(pImg)
                    frame+= 1
                    if frame % 500 == 0:
                        logger.debug(f"Image {scene.nb_images} frame {frame} of {nb_frames}")
                    progress.update()
                    for other_hash in image_hashes:
                        if hashes_are_similar(other_hash, phash):
                            break
                    else:
                        image_name= f"{phash}.jpg"
                        image_path= extract_directory.joinpath(image_name)
                        pImg.save(image_path)
                        pImg.thumbnail((downscale, downscale))
                        image_path= extract_directory_downscale.joinpath(image_name)
                        pImg.save(image_path)
                        scene.nb_images+= 1
                        image_hashes.append(phash)
                        if scene.nb_images == 1:
                            scene.downscale_width, scene.downscale_height= pImg.size

    except Exception as e:
        logger.error(f"extract_images Error extraction {location} : {e!s}")
        logger.exception(e)
    finally:
        if start is None:
            scene.extraction_time= None
        else:
            duration= (datetime.now() - start)
            scene.extraction_time = duration.total_seconds()
            logger.info(f"extract_images Extraction time : {duration}")
        if session is None:
            local_session.commit()
    logger.info(f"extract_images Extracted {scene.nb_images} over {nb_frames} frames")
    return True

# def analyse_extracted_video(detector, face_expand, dryrun, progress= None) -> List[ImageAnalysis]:
#     logger.info(f"analyse_extracted_video Detector: {detector} Extends: {face_expand}%")
#     if dryrun:
#         logger.warning(f"analyse_extracted_video DRY RUN, Proceding only on samples")
#     extract_directory= config.data_dir.joinpath('scene_extraction').joinpath('extracted_images')
#     if not extract_directory.exists():
#         gr.Warning("No data extracted, cannot process")
#         return [None, None, None]
    
#     images_metadata: List[ImageAnalysis]= []
#     for f in extract_directory.iterdir():
#         if not f.is_file():
#             continue
#         img_metadata= ImageAnalysis(f, f.stem, f.stem.endswith('_sample'))
#         if dryrun and not img_metadata.sample:
#             logger.debug(f"analyse_extracted_video dry run skip {img_metadata.name}")
#             continue
#         images_metadata.append(img_metadata)
    
#     total_count= len(images_metadata)
#     logger.info(f"analyse_extracted_video {total_count} image(s) to analyze")
#     if progress is not None:
#         progress(0, desc="Analyzing...", total=total_count, unit="image")
        
#     for index, metadata in enumerate(images_metadata):
#         if progress is not None:
#             progress(index/total_count)
        
#         try:
#             results= DeepFace.analyze(metadata.get_numpy(), actions=["age", "gender", "race"], enforce_detection=True, expand_percentage=face_expand)
#             for face_result in results:
#                 face= Face(x=face_result["region"]["x"],
#                         y= face_result["region"]["y"],
#                         w= face_result["region"]["w"],
#                         h= face_result["region"]["h"],
#                         age= face_result["age"],
#                         gender= face_result["dominant_gender"],
#                         gender_confidence=face_result["gender"][face_result["dominant_gender"]],
#                         race=face_result["dominant_race"],
#                         race_confidence=face_result["race"][face_result["dominant_race"]],
#                         confidence=face_result["face_confidence"]
#                         )
#                 other_face: Face
#                 for other_face in metadata.faces:
#                     if face.overlap(other_face):
#                         other_face.overlapping= True
#                         face.overlapping= True
#                 metadata.faces.append(face)
#             logger.debug(f"analyse_extracted_video Analyzed {metadata}")
#         except ValueError:
#             logger.info(f"analyse_extracted_video Image {metadata} has no face(s)")
#     return images_metadata