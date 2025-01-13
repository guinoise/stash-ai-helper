from utils.custom_logging import get_logger
logger= get_logger("utils.scene")

import gradio as gr
from stash_ai.config import config
import math
import cv2
import shutil


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
                    else:
                        image_path= extract_directory.joinpath(f"{nb_extracted:010}.jpg")
                    cv2.imwrite(image_path, image)
                    nb_extracted+= 1
                    logger.debug(f"Image {nb_extracted} / {nb_images} extracted to {image_path.name}")
                frame+= 1
                if progress is not None:
                    progress(frame/nb_frames)
        except Exception as e:
            logger.error(f"extract_images Error extraction {video} : {e!s}")
        logger.info(f"extract_images Extracted {nb_extracted} / {nb_images}")
        if nb_extracted < nb_images - 1:
            gr.Warning(f"Extracted only {nb_extracted} over {nb_images}")
    return images

def analyse_extracted_video(radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, checkbox_dryrun_face_detection, progress= None):
    logger.info(f"detect_and_extract_faces Detector: {radio_deepface_detector} Extends: {number_deepface_extends}% Min confidence: {number_deepface_min_confidence}")
    if checkbox_dryrun_face_detection:
        logger.warning(f"detect_and_extract_faces DRY RUN, Proceding only on samples")
    return [None, None, None]    