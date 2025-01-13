from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_scenes")

import gradio as gr
from stash_ai.config import config
from stash_ai.db import get_session
from stash_ai.model import StashBox, Performer, PerformerStashBoxImage
from utils.performer import get_performer_stash_image, load_performer, get_unknown_performer_image
from utils.scene import extract_video_images, analyse_extracted_video
import math

def detect_and_extract_faces(radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, checkbox_dryrun_face_detection, progress=gr.Progress()):
    return analyse_extracted_video(radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, checkbox_dryrun_face_detection, progress)
    #outputs=[gallery_face_dection, gallery_sample_faces, gallery_unique_faces]

#inputs=[text_video_url, number_duration, number_frames_per_second, number_extract_images_per_seconds, number_of_samples],
def extract_images(text_video_url, number_duration, number_frames_per_second, number_extract_images_per_seconds, number_of_samples, progress= gr.Progress()):
    nb_images= math.ceil(number_duration * number_extract_images_per_seconds)
    logger.info(f"extract_images URL: {text_video_url} Img per second : {number_extract_images_per_seconds} FPS: {number_frames_per_second} Total images: {nb_images} Samples: {number_of_samples}")
    return extract_video_images(text_video_url, number_duration, number_frames_per_second, number_extract_images_per_seconds, number_of_samples, progress)
    #outputs=[gallery_extracted]

#[number_frames_per_second, number_duration, number_extract_frames_per_seconds]
def calculate_nb_images_to_extract(number_frames_per_second, number_duration, number_extract_images_per_seconds):
    logger.info(f"calculate_frames_to_extract FPS: {number_frames_per_second} duration {number_duration} {number_extract_images_per_seconds} images per seconds")
    nb_images= math.ceil(number_duration * number_extract_images_per_seconds)
    logger.info(f"Nb images to extract {nb_images}")
    return [nb_images] #[number_images_to_extract]

def fetch_scene_from_stash(scene_id):
    logger.info(f"fetch_scene_from_stash : {scene_id}")
    scene= None
    html= None
    total_frames= 0
    frames_per_seconds= 0
    duration= 0
    url= None
    performers_images= []
    if config.stash_interface is None:
        gr.Warning("Not connected to stash")
    else:
        scene= config.stash_interface.find_scene(scene_id)
        html= ""
        if scene:
            url= scene.get("paths",{}).get("stream")
            html= f"""
            <h1>{scene.get('title')}</h1>
            <p>{scene.get('details')}</p>
            """
            for file_info in scene.get('files'):
                frames_per_seconds= file_info.get('frame_rate', 0)
                duration= file_info.get('duration', 0)
                total_frames= math.ceil(file_info.get('duration', 0) * file_info.get('frame_rate', 0))
                html+=f"""
                <p>Filename {file_info.get('basename')} duration: {file_info.get('duration')} seconds. Frame per seconds : {file_info.get('frame_rate')}. Total frames : {total_frames}</p>
                """
            for performer_data in scene.get('performers', []):
                performer_id= performer_data.get('id')
                logger.info(f"fetch_scene_from_stash Performer {performer_id}")
                if performer_id:
                    with get_session() as session:
                        performer= load_performer(performer_id, session)
                        performer_img= None
                        
                        if performer is not None:
                            performer_img= get_performer_stash_image(performer)
                            performer_text= f"{performer.name} [{performer.id}]"
                        else:
                            performer_text= f"Not found [{performer_id}]"
                        
                        if performer_img is None:
                            performer_img= get_unknown_performer_image()
                        
                        performers_images.append((performer_img, performer_text))
                        session.commit()
                        
                
                            
    return [scene, html, url, frames_per_seconds, duration, total_frames, performers_images]
    # outputs=[json_scene, html_scene_infos, text_video_url, number_frames_per_second, number_duration, number_total_frames]


def stash_scene_tab():
    with gr.Tab("Scenes", id="scene_main_tab") as scene_tab:
        state_search_scene= gr.BrowserState([])
        state_scene_stash= gr.BrowserState({"scene_ids": [], "current_index": None})
        with gr.Tabs(elem_id="scenes_tabs") as scenes_tabs:
            with gr.TabItem("Scene", id="scene_stash_tab"):
                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            with gr.Row():
                                txt_scene_id= gr.Number(label='Scene id', precision=0)
                                btn_load_scene_id= gr.Button(value='🔄', elem_classes="tool", min_width=10)
                            with gr.Row(visible=config.dev_mode):
                                with gr.Accordion(label="Dev", open=False):
                                    json_scene= gr.Json(label="Scene")
                            with gr.Row():
                                html_scene_infos= gr.HTML(label='Scene details', value='')
                            with gr.Row():
                                gallery_performers= gr.Gallery(interactive=False, object_fit='scale-down', height="15vh", label="Performers")                       
                            with gr.Row():
                                number_frames_per_second= gr.Number(label='Frame per seconds', interactive=False, value=0)
                                number_duration= gr.Number(label='Duration', interactive=False, value=0)
                                number_total_frames= gr.Number(label='Total frames', interactive=False, value=0)
                                number_images_to_extract= gr.Number(label='Number of images to extract', interactive=False, value=0)
                            with gr.Row():
                                text_video_url= gr.Text(label='Url', value=None)
                            with gr.Row():
                                with gr.Column(scale=4):
                                    with gr.Row():
                                        number_extract_images_per_seconds= gr.Number(label='Number of images to extract per seconds', step=0.01, value=1)
                                        number_of_samples= gr.Number(label="Number of samples", value=10, precision=0)
                                with gr.Column():
                                    btn_extract_images= gr.Button(value='Extract images', variant='primary')
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
                                with gr.Tabs():
                                    with gr.Tab("Samples face detection"):
                                        with gr.Row():
                                            with gr.Column(scale= 1):
                                                gallery_extracted= gr.Gallery(label='Samples extracted from scene', object_fit='contain', columns=2)
                                            with gr.Column(scale= 2):
                                                gallery_face_dection= gr.Gallery(label='Face detection on samples', object_fit='contain', columns=2)
                                    with gr.Tab("Extracted faces"):
                                        with gr.Row():
                                            with gr.Column():
                                                gallery_sample_faces= gr.Gallery(label='Face detection on samples', object_fit='contain')
                                            with gr.Column():
                                                gallery_unique_faces= gr.Gallery(label='Unique faces detected', object_fit='contain')
                                
        btn_detect_faces.click(detect_and_extract_faces,
                               inputs=[radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, checkbox_dryrun_face_detection],
                               outputs=[gallery_face_dection, gallery_sample_faces, gallery_unique_faces]
                               )
        
        btn_extract_images.click(extract_images,
                                 inputs=[text_video_url, number_duration, number_frames_per_second, number_extract_images_per_seconds, number_of_samples],
                                 outputs=[gallery_extracted]
                                 )
        
        btn_load_scene_id.click(fetch_scene_from_stash, 
                                inputs=[txt_scene_id], 
                                outputs=[json_scene, html_scene_infos, text_video_url, number_frames_per_second, number_duration, number_total_frames, gallery_performers]
                                ).then(
                                    calculate_nb_images_to_extract, 
                                    inputs=[number_frames_per_second, number_duration, number_extract_images_per_seconds], 
                                    outputs=[number_images_to_extract]
                                    )
        txt_scene_id.submit(fetch_scene_from_stash, 
                            inputs=[txt_scene_id], 
                            outputs=[json_scene, html_scene_infos, text_video_url, number_frames_per_second, number_duration, number_total_frames, gallery_performers]
                            ).then(
                                calculate_nb_images_to_extract,
                                inputs=[number_frames_per_second, number_duration, number_extract_images_per_seconds], 
                                outputs=[number_images_to_extract]
                                )
        number_extract_images_per_seconds.change(calculate_nb_images_to_extract, 
                                                 inputs=[number_frames_per_second, number_duration, number_extract_images_per_seconds], 
                                                 outputs=[number_images_to_extract]
                                                 )
        number_total_frames.change(calculate_nb_images_to_extract, 
                                   inputs=[number_frames_per_second, number_duration, number_extract_images_per_seconds], 
                                   outputs=[number_images_to_extract]
                                   )
