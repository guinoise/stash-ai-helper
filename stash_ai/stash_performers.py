from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_performers")

from typing import List, Dict
import gradio as gr
from stash_ai.config import config
from stash_ai.model import StashBox, Performer, PerformerStashBoxImage, Img, ImgFile, ImageAnalysis, DeepfaceFace, FaceStatus
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
    stash_images= []
    img_ids= []

    with get_session(expire_on_commit=False) as session:
        if config.dev_mode and config.stash_interface is not None:
            performer_json= config.stash_interface.find_performer(performer_id)
        performer: Performer= load_performer(performer_id, session)
        #performer: Performer= create_or_update_performer_from_stash(performer_id, None, session)
        logger.debug(f"Performer loaded : {performer}")
        if performer is None:
            raise gr.Error(f"Unable to load perfomer {performer_id}")
        performer_image= get_performer_stash_image(performer, session=session)
        for sbi in performer.stash_boxes_id:
            stash_ids+=f"{', ' if stash_ids else ''}{sbi.stash_box.name if sbi.stash_box else ''}: {sbi.stash_id}"
        stash_images, img_ids= get_downloaded_stash_box_images_for_performer(performer, session, return_tuple_ids=True)
        session.commit()
    state_performer_stash["image_ids"]= img_ids
    if state_performer_stash.get("current_index") is None or state_performer_stash.get("current_index") < len(stash_images):
        if len(img_ids) > 0:
            state_performer_stash["current_index"]= 0
        else:
            state_performer_stash["current_index"]=  None
    logger.debug(f"End: display_performer Current state : {type(state_performer_stash)} : {state_performer_stash}")        
    return [performer_id, performer_image, performer.name, stash_ids, performer_json, stash_images, state_performer_stash, None]
    

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

def handler_batch_create_dataset(radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, progress= gr.Progress(track_tqdm=True)):
    logger.info(f"handler_complete_deepface_analysis detector {radio_deepface_detector} face expand {number_deepface_extends}")
    columns=["Performer Id", "Performer Name", "ImgFile Id", "Group", "Confidence", "Image", "Face", "Status", "Size", "Age", "Gender", "Gender conf.", "Race", "Race conf."]    
    data= []
    index= []
    performers= []
    total_img= 0
    with get_session() as session:
        dataset_dir= config.data_dir.joinpath('dataset/performers')
        if dataset_dir.exists():
            shutil.rmtree(dataset_dir)
        dataset_dir.mkdir(parents=True)
        
        performer: Performer
        for perf_row in session.execute(select(Performer)).fetchall():
            performer= perf_row[0]
            performers.append(performer)
            total_img+= len(performer.images)
        
        t= progress.tqdm(range(total_img), desc='Processing...', total=total_img, unit='image')
        
        for performer in performers:
            for img in performer.images:
                t.update()
                if not img.original_file_exists():
                    continue
                img_file: ImgFile= img.original_file()
                analysis: ImageAnalysis= image_analysis(img_file, radio_deepface_detector, number_deepface_extends, session)
                face: DeepfaceFace
                for face in analysis.faces:
                    if face.overlapping:
                        continue
                    if face.confidence < number_deepface_min_confidence:
                        if face.performer is not None:
                            face.performer= None
                            session.add(face)
                        continue
                    if face.performer != performer:
                        face.performer= performer
                        session.add(face)
                    src=get_face_image_path(face)
                    dest_file= dataset_dir.joinpath(src.name)
                    shutil.copy(src, dest_file)
                    index.append(face.id)
                    data.append((face.performer.id, 
                                 face.performer.name, 
                                 img_file.id, 
                                 face.group, 
                                 face.confidence, 
                                 f"<img style='max-height: 75px;' src='/gradio_api/file={img_file.get_image_path()}'/>",                                  
                                 f"<img style='max-height: 75px;' src='/gradio_api/file={src}'/>", 
                                 face.status.value, 
                                 f"{face.w}x{face.h}",
                                 face.age, 
                                 face.gender, 
                                 face.gender_confidence,
                                 face.race,
                                 face.race_confidence))
        session.commit()
    return pd.DataFrame(data=data, index=index, columns=columns).to_html(escape=False)
    

def handler_batch_deepface_analysis(radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, progress= gr.Progress()):
    logger.info(f"handler_complete_deepface_analysis detector {radio_deepface_detector} face expand {number_deepface_extends}")
    columns=["Performer Id", "Performer Name", "ImgFile Id", "Group", "Confidence", "Image", "Face", "Status", "Size", "Age", "Gender", "Gender conf.", "Race", "Race conf."]    
    data= []
    index= []
    performers= []
    total_img= 0
    with get_session() as session:

        performer: Performer
        for perf_row in session.execute(select(Performer)).fetchall():
            performer= perf_row[0]
            performers.append(performer)
            total_img+= len(performer.images)
        
        #progress((0, total_img), desc='Processing...', total=total_img, unit='image')
        t= progress.tqdm(range(total_img), desc='Processing...', total=total_img, unit='image')
        for performer in performers:
            for img in performer.images:
                t.update()
                if not img.original_file_exists():
                    continue
                img_file: ImgFile= img.original_file()
                analysis: ImageAnalysis= image_analysis(img_file, radio_deepface_detector, number_deepface_extends, session)
                face: DeepfaceFace
                for face in analysis.faces:
                    if face.overlapping:
                        continue
                    if face.confidence < number_deepface_min_confidence and face.status in [FaceStatus.DISCOVERED, FaceStatus.AUTO_CONFIRMED]:
                        face.status= FaceStatus.AUTO_DISCARD
                        
                    if face.status in [FaceStatus.AUTO_DISCARD, FaceStatus.DISCARD]:
                        face_border_color= "#F3360D"
                    elif face.status == FaceStatus.CONFIRMED:
                        face_border_color= "#30F30D"
                    else:
                        face_border_color= "#1FA207"
                    index.append(face.id)
                    data.append((performer.id, 
                                 performer.name, 
                                 img_file.id, 
                                 face.group, 
                                 face.confidence, 
                                 f"<img style='max-height: 75px;' src='/gradio_api/file={img_file.get_image_path()}'/>",                                  
                                 f"<img style='max-height: 75px; border: 2px solid {face_border_color}' src='/gradio_api/file={get_face_image_path(face)}'/>", 
                                 face.status.value, 
                                 f"{face.w}x{face.h}",
                                 face.age, 
                                 face.gender, 
                                 face.gender_confidence, 
                                 face.race, 
                                 face.race_confidence))
        
    return pd.DataFrame(data=data, index=index, columns=columns).to_html(escape=False)

def handler_complete_deepface_analysis(performer_id, state_performer_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence):
    logger.info(f"handler_complete_deepface_analysis Performer id {performer_id} Current state : {state_performer_stash}")    
    logger.info(f"handler_complete_deepface_analysis detector {radio_deepface_detector} face expand {number_deepface_extends}")
    columns=["ImgFile Id", "Group", "Confidence", "Pic", "Face", "Status", "Size", "Age", "Gender", "Gender conf.", "Race", "Race conf."]    
    data= []
    index= []
    with get_session() as session:
        performer: Performer= load_performer(performer_id, session)
        if performer is None:
            gr.Warning(f"Unable to load performer {performer_id}")
            return None

        for img in performer.images:
            if not img.original_file_exists():
                continue
            img_file: ImgFile= img.original_file()
            analysis: ImageAnalysis= image_analysis(img_file, radio_deepface_detector, number_deepface_extends, session)
            face: DeepfaceFace
            for face in analysis.faces:
                if face.overlapping:
                    continue
                if face.confidence < number_deepface_min_confidence and face.status in [FaceStatus.DISCOVERED, FaceStatus.AUTO_CONFIRMED]:
                    face.status= FaceStatus.AUTO_DISCARD
                index.append(face.id)
                data.append((img_file.id, 
                             face.group, 
                             face.confidence, 
                             f"<img style='max-height: 75px;' src='/gradio_api/file={img_file.get_image_path()}'/>", 
                             f"<img style='max-height: 75px;' src='/gradio_api/file={get_face_image_path(face)}'/>", 
                             face.status.value,
                             f"{face.w}x{face.h}",
                             face.age, 
                             face.gender, 
                             face.gender_confidence, 
                             face.race, 
                             face.race_confidence))
        
    return pd.DataFrame(data=data, index=index, columns=columns).to_html(escape=False)
#                                            inputs=[txt_current_performer_id, state_peformer_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence],
def deepface_analysis(performer_id, state_performer_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, force):
    logger.debug(f"deepface_analysis Current state : {type(state_performer_stash)} : {state_performer_stash}")    
    #TODO Find why it become a list
    if isinstance(state_performer_stash, list):
        state_performer_stash= state_performer_stash[0]
    logger.info(f"deepface_analysis index {state_performer_stash.get("current_index")}")
    if not performer_id:
        gr.Warning(f"Invalid state, reload performer.")
        return [state_performer_stash, None, None, None]

    if state_performer_stash.get("image_ids") is None or len(state_performer_stash.get("image_ids")) < (state_performer_stash.get("current_index", -1)+1):
        gr.Warning(f"Invalid selection. Select an image from the stash images.")
        return [state_performer_stash, None, None, None]
    faces= []
    orig_img= None
    annotated_img= None
    with get_session() as session:
        img_file: ImgFile= None
        performer: Performer= load_performer(performer_id, session)
        if state_performer_stash.get("current_index", -1) == -1:
            gr.Info("Using main image")
            if not performer.main_image.original_file_exists():
                gr.Warning(f"Main performer file not on disk")
                return [state_performer_stash, None, None, None]
            img_file= performer.main_image.original_file()
        else:
            image_id= state_performer_stash.get("image_ids")[state_performer_stash.get("current_index")]
            logger.debug(f"Image id: {image_id}")
            img_file= session.get(ImgFile, image_id)
            if not img_file.exists():
                gr.Warning(f"ImgFile id {image_id} {img_file} not on disk")
                return [state_performer_stash, None, None, None]
            
        analysis: ImageAnalysis= image_analysis(img_file, radio_deepface_detector, number_deepface_extends, session, force) 
        face: DeepfaceFace
        for face in analysis.faces:
            if face.overlapping:
                continue
            faces.append((get_face_image_path(face), f"[{face.confidence}] {face.race} ({int(face.race_confidence)}) {face.gender} ({int(face.gender_confidence)}) {face.age} yo"))            
        orig_img= img_file.get_image_path()
        annotated_img= get_annotated_image_analysis_path(analysis, number_deepface_min_confidence)
        
    return [state_performer_stash, orig_img, annotated_img, faces]
    #outputs=[state_peformer_stash, img_performer, img_performer_overly, gallery_faces]

def main_image_selection(state_performer_stash, evt: gr.SelectData):
    logger.info(f"stash_image_selection : Index : {evt.index} Image ids list size : {len(state_performer_stash.get("image_ids", []))}")
    logger.debug(f"stash_main_image_selectionimage_selection Current state : {type(state_performer_stash)} : {state_performer_stash}")
    
    state_performer_stash["current_index"]= -1
    logger.debug(f"end stash_main_image_selectionimage_selection Current state : {type(state_performer_stash)} : {state_performer_stash}")    
    return [state_performer_stash]

def stash_image_selection(state_performer_stash, evt: gr.SelectData):
    logger.info(f"stash_image_selection : Index : {evt.index} Image ids list size : {len(state_performer_stash.get("image_ids", []))}")
    logger.debug(f"stash_image_selection Current state : {type(state_performer_stash)} : {state_performer_stash}")
    
    if len(state_performer_stash.get("image_ids", [])) < evt.index:
        gr.Warning("**Invalid state could not populate from images. Reload the performer.")
        return [state_performer_stash]
    state_performer_stash["current_index"]= evt.index
    logger.debug(f"end stash_image_selection Current state : {type(state_performer_stash)} : {state_performer_stash}")    
    return [state_performer_stash]

def performer_gallery_select(ids, evt: gr.SelectData):
    if evt.index > len(ids):
        gr.Warning("State invalid, could not retrieve selected image")
        return [ids[evt.index], gr.Tabs(selected=10)]
    logger.info(f"Performer id selected : {ids[evt.index]}")
    return [str(ids[evt.index]), gr.Tabs(selected="performer_stash_tab")]
    
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
                        img_performer_main= gr.Image(label='Main image')
                        gallery_performer_stash_images= gr.Gallery(label='Stash Images', object_fit='contain')
                    with gr.Column(scale=5):
                        with gr.Accordion(label="Dev", open=False):
                            json_performer= gr.Json(label="Stash box")
                        with gr.Row():
                            txt_current_performer_id= gr.Text(value= '', visible=False)
                            txt_performer_name= gr.Textbox(label='Performer name', interactive=False)
                            with gr.Group():
                                txt_performer_stashes= gr.Textbox(label='Stash box', interactive=False)
                                btn_download_images_from_stash_box= gr.Button(value= 'Download images from stash box', icon='assets/download.png', min_width=60)
                        with gr.Row():
                            with gr.Column(scale=2):
                                radio_deepface_detector= gr.Radio(choices=["retinaface", "mediapipe", "mtcnn", "dlib", "ssd", "opencv"], value="ssd", label='Detector')
                            with gr.Column(scale=1):
                                number_deepface_extends= gr.Number(label= "Extends % face detection", value=30)
                            with gr.Column(scale=1):
                                number_deepface_min_confidence= gr.Number(value=0.9, maximum=1, step=0.01, label="Minimum confidence")
                            # radio_deepface_analysis= gr.Radio(choices=["gender", "race", "emotion"],
                            #                                                                     value="gender",
                            #                                                                     label="Attributes",
                            #                                                                     info="Select an Attribute to Analyze")
                        with gr.Tabs():
                            with gr.Tab("Single file"):
                                with gr.Row():
                                    with gr.Column():
                                        btn_deepface_analysis= gr.Button(value='Deep face analysis', variant='primary')
                                        chk_force_analysis= gr.Checkbox(label="Force", value=False)
                                with gr.Row():
                                    with gr.Column(scale=1):
                                        img_performer= gr.Image()
                                    with gr.Column(scale=3):
                                        img_performer_overly= gr.Image()
                                    with gr.Column(scale=1):
                                        gallery_faces= gr.Gallery(label='Face(s)', rows=1)
                            with gr.Tab("Complete performer analysis"):
                                with gr.Row():
                                    with gr.Column():
                                        btn_deepface_analysis_global= gr.Button(value='Deep face analysis', variant='primary')
                                with gr.Row():
                                    with gr.Column():
                                        #df_face_results= gr.DataFrame()
                                        df_face_results= gr.HTML()
            with gr.Tab("Batch operation", id="performer_batch_tab"):
                with gr.Accordion(label="Update data", open=False):
                    btn_update_downloaded= gr.Button(value='Update all downloaded performers')
                    btn_download_all_stashbox_images= gr.Button(icon='assets/download.png', value='Download all images from stashbox for all performers')
                    html_result_batch= gr.HTML() 
                with gr.Row():
                    with gr.Column(scale=2):
                        radio_batch_deepface_detector= gr.Radio(choices=["retinaface", "mediapipe", "mtcnn", "dlib", "ssd", "opencv"], value="ssd", label='Detector')
                    with gr.Column(scale=1):
                        number_batch_deepface_expand= gr.Number(label= "Expand % face detection", value=30)
                    with gr.Column(scale=1):
                        number_batch_deepface_min_confidence= gr.Number(value=0.9, maximum=1, step=0.01, label="Minimum confidence")
                with gr.Row():
                    btn_deepface_analysis_batch= gr.Button(value='Deep face analysis', variant='primary')
                    btn_batch_create_dataset= gr.Button(value='Create dataset', variant='primary')
                with gr.Row():
                    df_batch_face_results= gr.HTML(value="<h1>Batch result</h1>")
                                       
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
                                               outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, gallery_performer_stash_images, state_peformer_stash, img_performer]
                                               )
        btn_load_performer_id.click(display_performer, 
                                    inputs=[state_peformer_stash, dd_performer_id], 
                                    outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, gallery_performer_stash_images, state_peformer_stash, img_performer]
                                    )
        # .then(deepface_analysis,
        #                                      inputs=[state_peformer_stash, radio_deepface_analysis],
        #                                      outputs=[state_peformer_stash, img_performer, plot_analysis, dataframe_analysis]
        #                                      )
        dd_performer_id.select(display_performer, 
                                inputs=[state_peformer_stash, dd_performer_id], 
                                outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, gallery_performer_stash_images, state_peformer_stash, img_performer]
                                )
        # .then(deepface_analysis,
        #                                      inputs=[state_peformer_stash, radio_deepface_analysis],
        #                                      outputs=[state_peformer_stash, img_performer, plot_analysis, dataframe_analysis]
        #                                      )
        btn_download_images_from_stash_box.click(download_images_from_stash_box, 
                                                inputs=[txt_current_performer_id, state_peformer_stash], 
                                                outputs=[gallery_performer_stash_images, state_peformer_stash]
                                                )
        img_performer_main.select(main_image_selection, 
                                    inputs=[state_peformer_stash], 
                                    outputs=[state_peformer_stash]
                                    ).then(deepface_analysis,
                                            inputs=[txt_current_performer_id, state_peformer_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence],
                                            outputs=[state_peformer_stash, img_performer, img_performer_overly, gallery_faces]
                                            )
        gallery_performer_stash_images.select(stash_image_selection, 
                                    inputs=[state_peformer_stash], 
                                    outputs=[state_peformer_stash]
                                    ).then(deepface_analysis,
                                            inputs=[txt_current_performer_id, state_peformer_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence],
                                            outputs=[state_peformer_stash, img_performer, img_performer_overly, gallery_faces]
                                            )
        btn_deepface_analysis.click(deepface_analysis,
                                    inputs=[txt_current_performer_id, state_peformer_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence, chk_force_analysis],
                                    outputs=[state_peformer_stash, img_performer, img_performer_overly, gallery_faces]
                                    )
        btn_deepface_analysis_global.click(handler_complete_deepface_analysis,
                                           inputs=[txt_current_performer_id, state_peformer_stash, radio_deepface_detector, number_deepface_extends, number_deepface_min_confidence],
                                           outputs=[df_face_results])
        btn_deepface_analysis_batch.click(handler_batch_deepface_analysis,
                                           inputs=[radio_batch_deepface_detector, number_batch_deepface_expand, number_batch_deepface_min_confidence],
                                           outputs=[df_batch_face_results])
        btn_batch_create_dataset.click(handler_batch_create_dataset,
                                           inputs=[radio_batch_deepface_detector, number_batch_deepface_expand, number_batch_deepface_min_confidence],
                                           outputs=[df_batch_face_results])
        btn_update_downloaded.click(update_all_performers, inputs=None, outputs=html_result_batch)
        btn_download_all_stashbox_images.click(download_all_stash_images, None, html_result_batch)

