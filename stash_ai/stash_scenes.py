from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_scenes")

import gradio as gr
from stash_ai.config import config
from stash_ai.db import get_session
from stash_ai.model import StashBox, Performer, PerformerStashBoxImage, Scene
from utils.performer import get_performer_stash_image, load_performer, get_unknown_performer_image
from utils.scene import load_scene, create_or_update_scene_from_stash, extract_scene_images, decord_scene
from utils.image import ImageAnalysis, Face
from datetime import timedelta
import random

def detect_and_extract_faces(radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, checkbox_dryrun_face_detection, progress=gr.Progress()):
    logger.info(f"detect_and_extract_faces")
    # results= analyse_extracted_video(radio_deepface_detector, number_deepface_extends, checkbox_dryrun_face_detection, progress)
    # logger.debug(f"detect_and_extract_faces {results}")
    gallery_face_dection= []
    gallery_sample_faces= []
    # metadata: ImageAnalysis
    # for metadata in results:
    #     if not metadata.sample:
    #         continue
    #     gallery_face_dection.append(metadata.get_numpy())
    #     gallery_face_dection.append(metadata.get_numpy_with_overlay(number_deepface_min_confidence))
    #     #gallery_sample_faces.extend(metadata.get_faces_numpy(number_deepface_min_confidence))
    # logger.info(f"analyse_extracted_video : Gallery faces : {len(gallery_face_dection)} Sample faces: {len(gallery_sample_faces)}")
    return [gallery_face_dection, gallery_sample_faces, None]
    #outputs=[gallery_face_dection, gallery_sample_faces, gallery_unique_faces]

def handle_load_samples(number_of_samples, state_scene_stash):
    logger.info(f"extract_images Samples {number_of_samples} state {state_scene_stash}")
    imgs= []
    if state_scene_stash.get('scene_id') is None:
        gr.Warning("Current scene id not found. Reload the scene.")
        return [None, state_scene_stash]
    with get_session(expire_on_commit=False) as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        files= list(scene.get_extract_dir().glob('*.jpg'))
        if len(files) > 0:
            imgs= random.choices(files, k=min(len(files), number_of_samples))
    return [imgs, state_scene_stash]   

     
#inputs=[number_of_samples, state_scene_stash],
def extract_images(number_downscale, number_hash_tolerance, state_scene_stash, progress= gr.Progress(track_tqdm=True)):
    logger.info(f"extract_images Downscale {number_downscale} Hash tolerance {number_hash_tolerance} state {state_scene_stash}")
    if state_scene_stash.get('scene_id') is None:
        gr.Warning("Current scene id not found. Reload the scene.")
        return [0, state_scene_stash]
    with get_session(expire_on_commit=False) as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        extract_scene_images(scene, hash_tolerance=number_hash_tolerance, downscale=number_downscale, session=session)
        #decord_scene(scene, hash_tolerance=number_hash_tolerance, downscale=number_downscale, session=session)
        session.commit()
           
    # nb_images= math.ceil(number_duration * number_extract_images_per_seconds)
    # logger.info(f"extract_images URL: {text_video_url} Img per second : {number_extract_images_per_seconds} FPS: {number_frames_per_second} Total images: {nb_images} Samples: {number_of_samples}")
    # return extract_video_images(text_video_url, number_duration, number_frames_per_second, number_extract_images_per_seconds, number_of_samples, progress)
    return [scene.nb_images, state_scene_stash]
    #outputs=[gallery_extracted, number_of_images, state_scene_stash]


def update_scene_infos(state_scene_stash):
    logger.info(f"update_scene_infos : {state_scene_stash.get('scene_id')}")
    with get_session(expire_on_commit=False) as session:
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
            if scene.downscale is not None:
                html += f"""
                <p>
                    <h2>Extraction information</h2>
                    <ul>
                        <li>Downscaled extraction {scene.downscale}</li>
                        <li>Dowscaled size {scene.downscale_width}x{scene.downscale_height}</li>
                        <li>Number of image extracted {scene.nb_images}</li>
                        <li>Hash tolerance during extraction {scene.hash_tolerance}</li>
                        <li>Extraction duration : {str(timedelta(seconds=scene.extraction_time)) if scene.extraction_time is not None else ''}
                    </ul>
                </p>
                """

            html+= f"""
            <p><a href="{scene.get_url()}" target="_blank">{scene.get_url()}</a>            
            """
            
            performer: Performer
            logger.debug(f"update_scene_infos Performers: {scene.performers}")
            for performer in scene.performers:
                performer_img= get_performer_stash_image(performer)
                performer_text= f"{performer.name} [{performer.id}]"                
                if performer_img is None:
                    performer_img= get_unknown_performer_image()
                performers_images.append((performer_img, performer_text))
        session.commit()
    return [html, performers_images, state_scene_stash]
    # outputs=[html_scene_infos, gallery_performers, state_scene_stash]
    
def handler_load_scene(scene_id, state_scene_stash):
    logger.info(f"handler_load_scene : {scene_id}")
    with get_session(expire_on_commit=False) as session:
        scene: Scene= create_or_update_scene_from_stash(scene_id, None, session)
        state_scene_stash["scene_id"]= scene.id
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
                                    number_downscale= gr.Number(label='Downscale to maximum height and width', precision=0, value=512)
                                    number_hash_tolerance= gr.Number(label='Hash tolerance', info='Higher number for less images', precision=0, value=20)
                                btn_extract_images= gr.Button(value='Extract images', variant='stop')
                            with gr.Column():
                                number_of_images= gr.Number(label='Number of images extracted', interactive=False)
                        with gr.Row():
                            with gr.Column(scale=4):
                                with gr.Row():
                                    radio_deepface_detector= gr.Radio(choices=["retinaface", "mediapipe", "yolov8"], value="yolov8")
                                    number_deepface_extends= gr.Number(label= "Extends % face detection", value=0)
                                    number_deepface_min_confidence= gr.Number(value=0.7, maximum=1, step=0.01, label="Minimum confidence")
                            with gr.Column():
                                btn_detect_faces= gr.Button(value='Detect and extract faces', variant='primary')
                                checkbox_dryrun_face_detection= gr.Checkbox(label='Dry run / Samples only', value=False)
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
                                        with gr.Column():
                                            gallery_sample_faces= gr.Gallery(label='Face detection on samples', object_fit='contain')
                                        with gr.Column():
                                            gallery_unique_faces= gr.Gallery(label='Unique faces detected', object_fit='contain')
                                
        # btn_detect_faces.click(detect_and_extract_faces,
        #                        inputs=[radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, checkbox_dryrun_face_detection],
        #                        outputs=[gallery_face_dection, gallery_sample_faces, gallery_unique_faces]
        #                        )
        
        btn_extract_images.click(extract_images,
                                 inputs=[number_downscale, number_hash_tolerance, state_scene_stash],
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
