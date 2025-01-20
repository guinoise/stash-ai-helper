from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_performers")

from typing import List, Dict
import gradio as gr
from stash_ai.config import config
from stash_ai.model import StashBox, Performer, PerformerStashBoxImage, Img, ImgFile, ImageAnalysis, DeepfaceFace, FaceStatus, ImageType
from stash_ai.db import get_session
from utils.performer import get_performer_stash_image, create_or_update_performer_from_stash, load_performer, download_stash_box_images_for_performer, get_downloaded_stash_box_images_for_performer, update_all_performers
from utils.performer import download_all_stash_images
from utils.image import image_analysis, get_annotated_image_analysis_path, get_face_image_path, get_face_phash, hashes_are_similar
from sqlalchemy import select
from sqlalchemy.orm import Session
import pandas as pd
import shutil
import re

FULL_SEARCH_ALLOWED=False

def download_images_from_stash_box(performer_id, state_peformer_stash):
    logger.info(f"Download images from stashbox for performer {performer_id}")
    images= None
    ids= []
    with get_session() as session:
        performer= load_performer(performer_id, session)
        logger.debug(f"Performer for download {performer}")
        download_stash_box_images_for_performer(performer, session)
        logger.debug(f"Performer for retrieve {performer}")
        images, ids= get_downloaded_stash_box_images_for_performer(performer, session, return_tuple_ids=True)
    state_peformer_stash["image_ids"]= ids
    if state_peformer_stash.get("current_index") is None or state_peformer_stash.get("current_index") < len(ids):
        if len(ids) == 0:
            state_peformer_stash["current_index"]= None
        else:
            state_peformer_stash["current_index"]= 0
    return [images, state_peformer_stash]
        
                    

def display_performer(state_performer_stash, performer: str):
    logger.info(f"display_performer {performer}")
    performer_id= 0
    if isinstance(performer, int):
        performer_id= performer
    else:
        id_search: re.Match= re.match('^\[([0-9]+)\].*', performer)
        if id_search:
            performer_id= int(id_search.group(1))
        elif performer.isdigit():
            performer_id= int(performer)
    logger.debug(f"Performer id : {performer_id}")
    logger.debug(f"display_performer Current state : {type(state_performer_stash)} : {state_performer_stash}")
    performer_image= None
    performer_json= None
    stash_ids= ""

    with get_session(expire_on_commit=False) as session:
        if config.dev_mode and config.stash_interface is not None:
            performer_json= config.stash_interface.find_performer(performer_id)
        performer: Performer= load_performer(performer_id, session)
        logger.debug(f"Performer loaded : {performer}")
        if performer is None:
            raise gr.Error(f"Unable to load perfomer {performer_id}")
        performer_image= get_performer_stash_image(performer, session=session)
        for sbi in performer.stash_boxes_id:
            stash_ids+=f"{', ' if stash_ids else ''}{sbi.stash_box.name if sbi.stash_box else ''}: {sbi.stash_id}"
        session.commit()
    logger.debug(f"End: display_performer Current state : {type(state_performer_stash)} : {state_performer_stash}")        
    return [performer_id, performer_image, performer.name, stash_ids, performer_json, state_performer_stash]

def search_performer_by_name(txt_performer_name):
    logger.info(f"Perform search on stash for name {txt_performer_name}")
    
    performers= None
    performers_images= []
    performers_ids= []
    if config.stash_interface is None:
        gr.Warning("Not connected to stash")
    elif txt_performer_name or FULL_SEARCH_ALLOWED:
        count, performers= config.stash_interface.find_performers(q=txt_performer_name, filter={"per_page": 50}, get_count=True)
        if count > 50:
            gr.Warning(f"Got {count} performers, only 50 first are displayed. Refine your research!")
        logger.info(f"Got {len(performers)} performer(s)")
        logger.debug(performers)
        with get_session() as session:
            for performer_data in performers:
                logger.info(f"Loading performer id {performer_data.get('id')}")
                performer: Performer= create_or_update_performer_from_stash(performer_data.get('id'), performer_data, session)
                img= get_performer_stash_image(performer, session= session)
                if img is None:
                    logger.error(f"Error img is none {performer.id}")
                else:
                    #img.thumbnail(SEARCH_IMG_MAX_SIZE)
                    performers_images.append((img, f"{performer.name} ({performer.id})"))
                    performers_ids.append(performer.id)
            session.commit()
    else:
        gr.Warning("Could not perform a full search.", duration=2)
    
    return [performers_images,performers, performers_ids]

def get_performers_list(session: Session= None):
    performers= []
    current_session= get_session() if session is None else session
    performer: Performer
    for perf_row in current_session.execute(select(Performer).order_by(Performer.name)).fetchall():
        performer= perf_row[0]
        #performers[performer.id]= f"[{performer.id}] {performer.name}"
        performers.append(f"[{performer.id}] {performer.name}")
    return performers

def handler_btn_refresh_performer_id(current_selection):
    performers= get_performers_list()
    selection= None
    if current_selection in performers:
        selection= current_selection
    return gr.Dropdown(choices=performers, value=selection)

def performer_gallery_select(ids, evt: gr.SelectData):
    if evt.index > len(ids):
        gr.Warning("State invalid, could not retrieve selected image")
        return [ids[evt.index], gr.Tabs(selected=10)]
    logger.info(f"Performer id selected : {ids[evt.index]}")
    return [str(ids[evt.index]), gr.Tabs(selected="performer_stash_tab")]

def update_face_status(face_id: int, face_status: str):
    logger.warning(f"update_face_status FaceId: {face_id} Status: {face_status} {FaceStatus(face_status)}")
    with get_session() as session:
        face= session.get(DeepfaceFace, face_id)
        face.status= FaceStatus(face_status)
        session.add(face)
        session.commit()
   
def stash_performers_tab():
    with gr.Tab("Performers", id="performer_main_tab") as performers_tab:
        state_search_performer= gr.BrowserState([])
        state_peformer_stash= gr.BrowserState({"image_ids": [], "current_index": None})
        with gr.Tabs(elem_id="performers_tabs") as performers_tabs:                        
            with gr.Tab("Search", id="performer_search_tab"):
                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            with gr.Row():
                                txt_search_performer_name= gr.Textbox(label='Performer name')
                                btn_search_performer_name= gr.Button(value='🔎', elem_classes="tool", min_width=10)
                logger.error(f"TO FIX ALWAYS VISIBLE : {config.dev_mode}")
                with gr.Row(visible=config.dev_mode):
                    with gr.Accordion(label="Dev", open=False):
                        json_performers_results= gr.Json(label="Performers results")
                with gr.Row():
                    with gr.Column():
                        gallery_search_performers= gr.Gallery(label='Performers', allow_preview=False, object_fit='contain', columns=4)                    
            with gr.Tab("Performer", id="performer_stash_tab"):
                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            with gr.Row():
                                with gr.Column(scale=10):
                                    with gr.Row():
                                        #txt_performer_id= gr.Number(label='Performer id', precision=0)
                                        dd_performer_id= gr.Dropdown(label="Performer id", allow_custom_value=True, choices=get_performers_list())
                                        btn_refresh_performer_id= gr.Button(value='🔄', elem_classes="tool", min_width=10)
                                with gr.Column():
                                    btn_load_performer_id= gr.Button(value='', icon='assets/load.ico', min_width=64)
                with gr.Row():
                    with gr.Column():
                        img_performer_main= gr.Image(label='Main image', interactive=False)
                        # gallery_performer_stash_images= gr.Gallery(label='Stash Images', object_fit='contain')
                    with gr.Column(scale=5):
                        with gr.Accordion(label="Dev", open=False):
                            json_performer= gr.Json(label="Stash box")
                        with gr.Row():
                            txt_current_performer_id= gr.Text(value= '', visible=False)
                            txt_performer_name= gr.Textbox(label='Performer name', interactive=False)
                            with gr.Group():
                                txt_performer_stashes= gr.Textbox(label='Stash box', interactive=False)
                                btn_download_images_from_stash_box= gr.Button(value= 'Download images from stash box', icon='assets/download.png', min_width=60)
                            number_deepface_min_confidence= gr.Number(value=0.9, maximum=1, step=0.01, label="Minimum confidence")
                        @gr.render(inputs= [txt_current_performer_id, number_deepface_min_confidence],
                                   triggers=[btn_load_performer_id.click, txt_current_performer_id.change, btn_download_images_from_stash_box.click])
                        def render_images(performer_id, min_confidence):
                            with get_session(expire_on_commit=False) as session:
                                performer: Performer= load_performer(performer_id, session)
                                logger.debug(f"render_images Performer loaded : {performer}")
                                if performer is None:
                                    raise gr.Error(f"Unable to load perfomer {performer_id}")
                                with gr.Row():
                                    gr.HTML(value=f"<p>Detector : {config.face_recognition_model} face expands {config.expand_face} %</p>")
                                for img in performer.images:
                                    if img.image_type == ImageType.STASH_BOX_PERFORMER or img.phash == performer.main_image_phash:
                                        if not img.original_file_exists():
                                            logger.warning(f"Image not on disk {img.phash}")
                                            continue
                                        img_file= img.original_file()
                                        analysis= image_analysis(img_file=img_file, detector=config.face_recognition_model, face_expand=config.expand_face, session=session)
                                        with gr.Row():
                                            with gr.Column():
                                                with gr.Group():
                                                    with gr.Column():
                                                        gr.Image(height="250px", value=img_file.get_image_path().resolve())
                                                        gr.HTML(value=f"<p>Size {img_file.width}x{img_file.height}</p>")
                                            with gr.Column():
                                                gr.Image(height="250px", value=get_annotated_image_analysis_path(analysis, min_confidence))
                                            with gr.Column():
                                                for face in analysis.faces:
                                                    txt_face_id= gr.Text(visible=False, value=face.id)
                                                    with gr.Group():
                                                        with gr.Row():
                                                            gr.Image(value=get_face_image_path(face), height="250px")
                                                        with gr.Row():
                                                            dd_face_status= gr.Dropdown(choices=[s.value for s in FaceStatus], value=face.status.value, label='Face status')
                                                            dd_face_status.change(update_face_status, inputs=[txt_face_id, dd_face_status])
                                                        with gr.Row():
                                                            gr.HTML(value=f"""
                                                                    <p>Size {face.w}x{face.h}</p>
                                                                    <p>Confidence : {round(face.confidence, 3)}</p>
                                                                    <p>{face.age} yo
                                                                    {face.race} ({round(face.race_confidence, 3)})
                                                                    {face.gender} ({round(face.gender_confidence,3)})
                                                                    </p>
                                                                    """)
                                session.commit()
            with gr.Tab("Batch operation", id="performer_batch_tab"):
                with gr.Accordion(label="Update data", open=False):
                    btn_update_downloaded= gr.Button(value='Update all downloaded performers')
                    btn_download_all_stashbox_images= gr.Button(icon='assets/download.png', value='Download all images from stashbox for all performers')
                    html_result_batch= gr.HTML() 
                with gr.Row():
                    with gr.Column(scale=1):
                        number_batch_deepface_min_confidence= gr.Number(value=0.9, maximum=1, step=0.01, label="Minimum confidence")
                with gr.Row():
                    chk_create_dataset= gr.Checkbox(label='Create dataset', value=False)
                    btn_deepface_analysis_batch= gr.Button(value='Deep face analysis', variant='primary')
                with gr.Row():
                    with gr.Column():
                        @gr.render(inputs= [number_batch_deepface_min_confidence, chk_create_dataset], triggers=[btn_deepface_analysis_batch.click])
                        def render_images_all(min_confidence, create_dataset):
                            logger.info("Render all performers")
                            if create_dataset:
                                dataset_dir= config.data_dir.joinpath('dataset/performers')
                                if dataset_dir.exists():
                                    shutil.rmtree(dataset_dir)
                                dataset_dir.mkdir(parents=True)                            
                            with get_session() as session:
                                performer: Performer
                                for perf_row in session.execute(select(Performer)).fetchall():
                                    performer= perf_row[0]
                                    logger.info(f"render_images (all) Performer loaded : {performer}")
                                    with gr.Row():
                                        with gr.Column():
                                            gr.HTML(value=f"<hr/><h2>[{performer.id}] {performer.name}</h2>")
                                    for img in performer.images:
                                        if img.image_type == ImageType.STASH_BOX_PERFORMER or img.phash == performer.main_image_phash:
                                            if not img.original_file_exists():
                                                logger.warning(f"Image not on disk {img.phash}")
                                                continue
                                            img_file= img.original_file()
                                            analysis= image_analysis(img_file=img_file, detector=config.face_recognition_model, face_expand=config.expand_face, session=session)
                                            with gr.Row():
                                                with gr.Column():
                                                    with gr.Group():
                                                        with gr.Column():
                                                            gr.Image(height="100px", value=img_file.get_image_path().resolve())
                                                            gr.HTML(value=f"<p>Size {img_file.width}x{img_file.height}</p>")
                                                with gr.Column():
                                                    gr.Image(height="100px", value=get_annotated_image_analysis_path(analysis, min_confidence))
                                                with gr.Column():
                                                    for face in analysis.faces:
                                                        txt_face_id= gr.Text(visible=False, value=face.id)
                                                        in_dataset= True
                                                        if face.confidence < min_confidence and face.status not in [FaceStatus.AUTO_DISCARD, FaceStatus.DISCARD]:
                                                            face.status= FaceStatus.AUTO_DISCARD
                                                            session.add(face)
                                                                                                                    
                                                        if face.status in [FaceStatus.AUTO_DISCARD, FaceStatus.DISCARD]:
                                                            face_border_color= "#F3360D"
                                                            in_dataset= False
                                                        elif face.status == FaceStatus.CONFIRMED:
                                                            face_border_color= "#30F30D"
                                                        else:
                                                            face_border_color= "#1FA207" 
                                                        if create_dataset and in_dataset:
                                                            src=get_face_image_path(face)
                                                            dest_file= dataset_dir.joinpath(src.name)
                                                            shutil.copy(src, dest_file)                                                                                                                   
                                                        with gr.Group():
                                                            with gr.Row():
                                                                gr.Image(value=get_face_image_path(face), height="100px")
                                                            with gr.Row():
                                                                dd_face_status= gr.Dropdown(choices=[s.value for s in FaceStatus], value=face.status.value, label='Face status')
                                                                dd_face_status.change(update_face_status, inputs=[txt_face_id, dd_face_status])
                                                            with gr.Row():
                                                                gr.HTML(value=f"""
                                                                        <p style='color: {face_border_color};'>Size {face.w}x{face.h}</p>
                                                                        <p style='color: {face_border_color};'>Confidence : {round(face.confidence, 3)}</p>
                                                                        <p style='color: {face_border_color};'>{face.age} yo
                                                                        {face.race} ({round(face.race_confidence, 3)})
                                                                        {face.gender} ({round(face.gender_confidence,3)})
                                                                        </p>
                                                                        """)
                                session.commit()

                                       
        btn_refresh_performer_id.click(handler_btn_refresh_performer_id, inputs=[dd_performer_id], outputs=[dd_performer_id])                
        btn_search_performer_name.click(search_performer_by_name, 
                                        inputs=[txt_search_performer_name], 
                                        outputs=[gallery_search_performers, json_performers_results, state_search_performer]
                                        )
        txt_search_performer_name.submit(search_performer_by_name, 
                                        inputs=[txt_search_performer_name], 
                                        outputs=[gallery_search_performers, json_performers_results, state_search_performer]
                                        )
        gallery_search_performers.select(performer_gallery_select, 
                                        inputs=[state_search_performer], 
                                        outputs=[dd_performer_id, performers_tabs]
                                        ).then(display_performer, 
                                               inputs=[state_peformer_stash, dd_performer_id], 
                                               outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, state_peformer_stash]
                                               )
        btn_load_performer_id.click(display_performer, 
                                    inputs=[state_peformer_stash, dd_performer_id], 
                                    outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, state_peformer_stash]
                                    )
        dd_performer_id.select(display_performer, 
                                inputs=[state_peformer_stash, dd_performer_id], 
                                outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, state_peformer_stash]
                                )
        btn_download_images_from_stash_box.click(download_images_from_stash_box, 
                                                inputs=[txt_current_performer_id, state_peformer_stash], 
                                                outputs=[state_peformer_stash]
                                                )
        btn_update_downloaded.click(update_all_performers, inputs=None, outputs=html_result_batch)
        btn_download_all_stashbox_images.click(download_all_stash_images, None, html_result_batch)

