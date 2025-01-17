from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_scenes", True)

import gradio as gr
from stash_ai.config import config
from stash_ai.db import get_session
from stash_ai.model import StashBox, Performer, PerformerStashBoxImage, Scene, Img, ImgFile
from utils.performer import get_performer_stash_image, load_performer, get_unknown_performer_image
from utils.scene import load_scene, create_or_update_scene_from_stash, extract_scene_images, decord_scene
from utils.image import ImageAnalysis, Face
from datetime import timedelta
import random
from PIL import Image
import utils.image as util_img
from tqdm import tqdm 
from typing import List
import imagehash

def detect_and_extract_faces(state_scene_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, checkbox_dryrun_face_detection, number_hash_tolerance, number_of_samples, progress=gr.Progress(track_tqdm=True)):
    logger.info(f"detect_and_extract_faces state {state_scene_stash}, detector {radio_deepface_detector} expand {number_deepface_extends} min_confidence {number_deepface_min_confidence} dryrun {checkbox_dryrun_face_detection} nb samples {number_of_samples}, hash tolerance {number_hash_tolerance}")
    # results= analyse_extracted_video(radio_deepface_detector, number_deepface_extends, checkbox_dryrun_face_detection, progress)
    # logger.debug(f"detect_and_extract_faces {results}")
    gallery_face_dection= []
    gallery_sample_faces= []
    gallery_unique_faces= []
    faces_hashes= []
    infos_html= ""
    if state_scene_stash.get('scene_id') is None:
        gr.Warning("Current scene id not found. Reload the scene.")
        return [gallery_face_dection, gallery_sample_faces, gallery_unique_faces, infos_html]
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        imgs: List[Img]= []
        if checkbox_dryrun_face_detection:
            imgs= random.choices(scene.images, k=min(len(scene.images), number_of_samples))
        else:
            imgs= scene.images

        img: Img            
        for img in tqdm(imgs, desc='Processing...', unit='image'):
            logger.debug(f"detect_and_extract_faces Detection on {img}")
            if not img.original_file_exists():
                logger.warning(f"detect_and_extract_faces File not on disk : {img}")
                continue
            im= Image.open(img.original_file().get_image_path())
            analysis: util_img.ImageAnalysis= util_img.image_analysis(im, radio_deepface_detector, number_deepface_extends)
            face: util_img.Face
            gallery_face_dection.append(im)
            gallery_face_dection.append(analysis.get_numpy_with_overlay(number_deepface_min_confidence))
            for face, face_im in analysis.get_faces_pil(number_deepface_min_confidence):
                hash= imagehash.phash(face_im)
                for oh in faces_hashes:
                    if util_img.hashes_are_similar(hash, oh, number_hash_tolerance):
                        break
                else:
                    gallery_unique_faces.append((face_im, f"[{face.confidence}] {face.race} ({int(face.race_confidence)}) {face.gender} ({int(face.gender_confidence)}) {face.age} yo"))
                faces_hashes.append(hash)
                gallery_sample_faces.append((face_im, f"[{face.confidence}] {face.race} ({int(face.race_confidence)}) {face.gender} ({int(face.gender_confidence)}) {face.age} yo"))
        infos_html+= f"""
            <p>Images analyzed : {len(imgs)}</p>
            <p>Faces extracted : {len(gallery_sample_faces)}</p>
            <p>Unique faces : {len(gallery_unique_faces)}</p>
        """
    # metadata: ImageAnalysis
    # for metadata in results:
    #     if not metadata.sample:
    #         continue
    #     gallery_face_dection.append(metadata.get_numpy())
    #     gallery_face_dection.append(metadata.get_numpy_with_overlay(number_deepface_min_confidence))
    #     #gallery_sample_faces.extend(metadata.get_faces_numpy(number_deepface_min_confidence))
    # logger.info(f"analyse_extracted_video : Gallery faces : {len(gallery_face_dection)} Sample faces: {len(gallery_sample_faces)}")
    return [gallery_face_dection, gallery_sample_faces, gallery_unique_faces, infos_html]
    #outputs=[gallery_face_dection, gallery_sample_faces, gallery_unique_faces]

def handle_load_samples(number_of_samples, state_scene_stash):
    logger.info(f"extract_images Samples {number_of_samples} state {state_scene_stash}")
    imgs= []
    if state_scene_stash.get('scene_id') is None:
        gr.Warning("Current scene id not found. Reload the scene.")
        return [None, state_scene_stash]
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        if len(scene.images) > 0:
            img: Img
            for img in random.choices(scene.images, k=min(len(scene.images), number_of_samples)):
                if img.original_file_exists():
                    imgs.append(Image.open(img.original_file().get_image_path()))
    return [imgs, state_scene_stash]   

     
#inputs=[number_of_samples, state_scene_stash],
def extract_images(number_hash_tolerance, state_scene_stash, progress= gr.Progress(track_tqdm=True)):
    logger.info(f"extract_images Hash tolerance {number_hash_tolerance} state {state_scene_stash}")
    nb_images= 0
    if state_scene_stash.get('scene_id') is None:
        gr.Warning("Current scene id not found. Reload the scene.")
        return [0, state_scene_stash]
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        extract_scene_images(scene, hash_tolerance=number_hash_tolerance, session=session)
        nb_images= scene.nb_images
        #decord_scene(scene, hash_tolerance=number_hash_tolerance, downscale=number_downscale, session=session)
        session.commit()
           
    # nb_images= math.ceil(number_duration * number_extract_images_per_seconds)
    # logger.info(f"extract_images URL: {text_video_url} Img per second : {number_extract_images_per_seconds} FPS: {number_frames_per_second} Total images: {nb_images} Samples: {number_of_samples}")
    # return extract_video_images(text_video_url, number_duration, number_frames_per_second, number_extract_images_per_seconds, number_of_samples, progress)
    return [nb_images, state_scene_stash]
    #outputs=[gallery_extracted, number_of_images, state_scene_stash]


def update_scene_infos(state_scene_stash):
    logger.info(f"update_scene_infos : {state_scene_stash.get('scene_id')}")
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        performers_images= []
        html= ""
        if scene:
            html= f"""
            <h1>{scene.title}</h1>
            <p>{scene.details}</p>
            <p>
                <h2>Media information</h2>
                <ul>
                    <li>File {scene.local_file_name}</li>
                    <li>Codec {scene.video_codec}</li>
                    <li>Size {scene.width}x{scene.height}</li>
                    <li>Duration {scene.duration} seconds</li>
                    <li>FPS {scene.fps}</li>
                    <li>{scene.number_of_frames()} frames</li>
                </ul>
            </p>
            """
            if scene.nb_images:
                html += f"""
                <p>
                    <h2>Extraction information</h2>
                    <ul>
                        <li>Number of image extracted {scene.nb_images}</li>
                        <li>Hash tolerance during extraction {scene.hash_tolerance}</li>
                        <li>Extraction duration : {str(timedelta(seconds=scene.extraction_time)) if scene.extraction_time is not None else ''}
                    </ul>
                </p>
                """

            # if scene.downscale is not None:
            #     html += f"""
            #     <p>
            #         <h2>Extraction information</h2>
            #         <ul>
            #             <li>Downscaled extraction {scene.downscale}</li>
            #             <li>Dowscaled size {scene.downscale_width}x{scene.downscale_height}</li>
            #             <li>Number of image extracted {scene.nb_images}</li>
            #             <li>Hash tolerance during extraction {scene.hash_tolerance}</li>
            #             <li>Extraction duration : {str(timedelta(seconds=scene.extraction_time)) if scene.extraction_time is not None else ''}
            #         </ul>
            #     </p>
            #     """

            html+= f"""
            <p><a href="{scene.get_url()}" target="_blank">{scene.get_url()}</a>            
            """
            
            performer: Performer
            logger.debug(f"update_scene_infos Performers: {scene.performers}")
            for performer in scene.performers:
                performer_img= get_performer_stash_image(performer, session=session)
                performer_text= f"{performer.name} [{performer.id}]"                
                if performer_img is None:
                    performer_img= get_unknown_performer_image()
                performers_images.append((performer_img, performer_text))
        session.commit()
    return [html, performers_images, state_scene_stash]
    # outputs=[html_scene_infos, gallery_performers, state_scene_stash]
    
def handler_load_scene(scene_id, state_scene_stash):
    logger.info(f"handler_load_scene : {scene_id}")
    with get_session() as session:
        scene: Scene= create_or_update_scene_from_stash(scene_id, None, session)
        state_scene_stash["scene_id"]= scene.id if scene is not None else None
        session.commit()
    logger.debug(f"handler_load_scene out state : {state_scene_stash}")
    return state_scene_stash

    # outputs=[html_scene_infos, gallery_performers, state_scene_stash]


def stash_scene_tab():
    with gr.Tab("Scenes", id="scene_main_tab") as scene_tab:
        state_search_scene= gr.BrowserState([])
        state_scene_stash= gr.BrowserState({"scene_id": None})
        with gr.Tabs(elem_id="scenes_tabs") as scenes_tabs:
            with gr.TabItem("Scene", id="scene_stash_tab"):
                with gr.Row():
                    with gr.Column():
                        with gr.Row():
                            txt_scene_id= gr.Number(label='Scene id', precision=0)
                            btn_load_scene_id= gr.Button(value='🔄', elem_classes="tool", min_width=10)
                        with gr.Row():
                            with gr.Group():
                                html_scene_infos= gr.HTML(label='Scene details', value='')
                        with gr.Row():
                            gallery_performers= gr.Gallery(interactive=False, object_fit='scale-down', height="15vh", label="Performers", columns=10)                       
                        with gr.Row():
                            with gr.Column(scale=4):
                                with gr.Row():
                                    number_hash_tolerance= gr.Number(label='Hash tolerance', info='Higher number for less images', precision=0, value=20)
                                btn_extract_images= gr.Button(value='Extract images', variant='stop')
                            with gr.Column():
                                number_of_images= gr.Number(label='Number of images extracted', interactive=False)
                        with gr.Row():
                            with gr.Column(scale=4):
                                with gr.Row():
                                    radio_deepface_detector= gr.Radio(choices=["retinaface", "mediapipe", "mtcnn", "dlib"], value="mtcnn", label='Detector')
                                    number_deepface_extends= gr.Number(label= "Extends % face detection", value=30)
                                    number_deepface_min_confidence= gr.Number(value=0.9, maximum=1, step=0.01, label="Minimum confidence")
                            with gr.Column():
                                btn_detect_faces= gr.Button(value='Detect and extract faces', variant='primary')
                                checkbox_dryrun_face_detection= gr.Checkbox(label='Dry run / Samples only', value=True)
                        with gr.Row():
                            number_of_samples= gr.Number(label='Number of samples', precision=0, value=10)
                            btn_load_samples= gr.Button(value='Load samples')

                        with gr.Row():
                            with gr.Tabs():
                                with gr.Tab("Samples face detection"):
                                    with gr.Row():
                                        with gr.Column(scale= 1):
                                            gallery_extracted= gr.Gallery(label='Samples extracted from scene', object_fit='contain', columns=1)
                                        with gr.Column(scale= 2):
                                            gallery_face_dection= gr.Gallery(label='Face detection on samples', object_fit='contain', columns=2)
                                with gr.Tab("Extracted faces"):
                                    with gr.Row():
                                        html_analysis_infos= gr.HTML(label='Information')
                                    with gr.Row():
                                        with gr.Column():
                                            gallery_sample_faces= gr.Gallery(label='Face detection on samples', object_fit='contain')
                                        with gr.Column():
                                            gallery_unique_faces= gr.Gallery(label='Unique faces detected', object_fit='contain')
                                
        btn_detect_faces.click(detect_and_extract_faces,
                               inputs=[state_scene_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, checkbox_dryrun_face_detection, number_hash_tolerance, number_of_samples],
                               outputs=[gallery_face_dection, gallery_sample_faces, gallery_unique_faces, html_analysis_infos]
                               )
        
        btn_extract_images.click(extract_images, 
                                 inputs=[number_hash_tolerance, state_scene_stash],
                                 outputs=[number_of_images, state_scene_stash]
                                 ).then(update_scene_infos, 
                                        inputs=state_scene_stash, 
                                        outputs=[html_scene_infos, gallery_performers, state_scene_stash]
                                        ).then(handle_load_samples,
                                               inputs=[number_of_samples, state_scene_stash],
                                               outputs=[gallery_extracted, state_scene_stash]
                                               )
        btn_load_samples.click(handle_load_samples,
                               inputs=[number_of_samples, state_scene_stash],
                               outputs=[gallery_extracted, state_scene_stash]
                               )
        btn_load_scene_id.click(handler_load_scene, 
                                inputs=[txt_scene_id, state_scene_stash], 
                                outputs=[state_scene_stash]
                                ).then(update_scene_infos, inputs=state_scene_stash, outputs=[html_scene_infos, gallery_performers, state_scene_stash])
        
        txt_scene_id.submit(handler_load_scene, 
                            inputs=[txt_scene_id, state_scene_stash], 
                            outputs=[state_scene_stash]
                            ).then(update_scene_infos, inputs=state_scene_stash, outputs=[html_scene_infos, gallery_performers, state_scene_stash])
        # number_extract_images_per_seconds.change(calculate_nb_images_to_extract, 
        #                                          inputs=[number_frames_per_second, number_duration, number_extract_images_per_seconds], 
        #                                          outputs=[number_images_to_extract]
        #                                          )
        # number_total_frames.change(calculate_nb_images_to_extract, 
        #                            inputs=[number_frames_per_second, number_duration, number_extract_images_per_seconds], 
        #                            outputs=[number_images_to_extract]
        #                            )
