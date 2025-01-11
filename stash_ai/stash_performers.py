from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_performers")

from typing import List, Dict
import gradio as gr
from stash_ai.config import config
from stash_ai.model import StashBox, Performer, PerformerStashBoxImage
from stash_ai.db import get_session
from utils.performer import get_performer_stash_image, create_or_update_performer_from_stash, load_performer, download_stash_box_images_for_performer, get_downloaded_stash_box_images_for_performer
from sqlalchemy import select
from PIL import Image

def download_images_from_stash_box(performer_id):
    logger.info(f"Download images from stashbox for performer {performer_id}")
    images= None
    ids= []
    with get_session() as session:
        performer= load_performer(performer_id, session)
        logger.debug(f"Performer for download {performer}")
        download_stash_box_images_for_performer(performer, session)
        logger.debug(f"Performer for retrieve {performer}")
        images, ids= get_downloaded_stash_box_images_for_performer(performer, session, return_tuple_ids=True)
    return [images, ids]
        
                    

def display_performer(performer_id: int):
    logger.info(f"Dispaly performer {performer_id}")
    performer_image= None
    performer_name= None
    performer_json= None
    stash_ids= ""
    stash_images= None
    img_ids= []

    with get_session(expire_on_commit=False) as session:
        if config.dev_mode and config.stash_interface is not None:
            performer_json= config.stash_interface.find_performer(performer_id)
        performer: Performer= load_performer(performer_id, session)
        logger.debug(f"Performer loaded : {performer}")
        if performer is None:
            raise gr.Error(f"Unable to load perfomer {performer_id}")
        performer_image= get_performer_stash_image(performer)
        for sbi in performer.stash_boxes_id:
            stash_ids+=f"{', ' if stash_ids else ''}{sbi.stash_box.name}: {sbi.stash_id}"
        stash_images, img_ids= get_downloaded_stash_box_images_for_performer(performer, session, return_tuple_ids=True)
        session.commit()
        
    return [performer_id, performer_image, performer.name, stash_ids, performer_json, stash_images, img_ids, None]
    

def search_performer_by_name(txt_performer_name):
    logger.info(f"Perform search on stash for name {txt_performer_name}")
    
    performers= None
    performers_images= []
    performers_ids= []
    if config.stash_interface is None:
        gr.Warning("Not connected to stash")
    elif txt_performer_name:
        count, performers= config.stash_interface.find_performers(q=txt_performer_name, filter={"per_page": 50}, get_count=True)
        if count > 50:
            gr.Warning(f"Got {count} performers, only 50 first are displayed. Refine your research!")
        logger.info(f"Got {len(performers)} performer(s)")
        logger.debug(performers)
        with get_session() as session:
            for performer_data in performers:
                logger.info(f"Loading performer id {performer_data.get('id')}")
                performer: Performer= create_or_update_performer_from_stash(performer_data.get('id'), performer_data, session)
                img= get_performer_stash_image(performer)
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

def stash_image_selection(gallery, img_ids, evt: gr.SelectData):
    logger.info(f"Performer stash selection : {gallery} {evt!r}")
    logger.info(f"You selected {evt.value} at {evt.index} from {evt.target}")
    if len(img_ids) < evt.index:
        raise gr.Error("Invalid state could not populate from images. Reload the performer.")
    logger.info(f"Image id : {img_ids[evt.index]}")
    img_id= (img_ids[evt.index]["image_id"], img_ids[evt.index]["performer_id"], img_ids[evt.index]["stash_box_id"])
    logger.debug(f"Image id : {img_id}")
    img= None
    with get_session() as session:
        img_data: PerformerStashBoxImage= session.get(PerformerStashBoxImage, img_id)
        if img_data is not None:
            img= Image.open(img_data.get_image_path())

    return [img, None]

def performer_gallery_select(selection, ids, evt: gr.SelectData):
    if evt.index > len(ids):
        raise gr.Error("State invalid, could not retrieve selected image")
    logger.info(f"Performer id selected : {ids[evt.index]}")
    return [ids[evt.index], gr.Tabs(selected=10)]
    
def stash_performers_tab():
    state_search_performer= gr.BrowserState([])
    state_peformer_stash= gr.BrowserState([])
    with gr.Tab("Performers") as performers_tab:
        with gr.Tabs() as main_tab:
            with gr.TabItem("Performer", id=10):
                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            with gr.Row():
                                txt_performer_id= gr.Number(label='Performer id', precision=0)
                                btn_load_performer_id= gr.Button(value='🔄', elem_classes="tool", min_width=10)
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
                            with gr.Column():
                                img_performer= gr.Image()
                            with gr.Column():
                                plot_analysis= gr.Plot()
                        

            with gr.TabItem("Search", id=11):
                with gr.Row():
                    with gr.Column():
                        with gr.Group():
                            with gr.Row():
                                txt_search_performer_name= gr.Textbox(label='Performer name')
                                btn_search_performer_name= gr.Button(value='🔎', elem_classes="tool", min_width=10)

                with gr.Row(visible=config.dev_mode):
                    with gr.Accordion(label="Dev", open=False):
                        json_performers_results= gr.Json(label="Performers results")
                with gr.Row():
                    with gr.Column():
                        gallery_search_performers= gr.Gallery(label='Performers', allow_preview=False, object_fit='contain', columns=4)                    
                    
    btn_search_performer_name.click(search_performer_by_name, 
                                    inputs=[txt_search_performer_name], 
                                    outputs=[gallery_search_performers, json_performers_results, state_search_performer]
                                    )
    txt_search_performer_name.submit(search_performer_by_name, 
                                     inputs=[txt_search_performer_name], 
                                     outputs=[gallery_search_performers, json_performers_results, state_search_performer]
                                     )
    gallery_search_performers.select(performer_gallery_select, 
                                     inputs=[gallery_search_performers, state_search_performer], 
                                     outputs=[txt_performer_id, main_tab]
                                     ).then(
                                         display_performer, 
                                         inputs=[txt_performer_id], 
                                         outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, gallery_performer_stash_images, state_peformer_stash, img_performer]
                                         )
    btn_load_performer_id.click(display_performer, 
                                inputs=[txt_performer_id], 
                                outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, gallery_performer_stash_images, state_peformer_stash, img_performer]
                                )
    txt_performer_id.submit(display_performer, 
                            inputs=[txt_performer_id], 
                            outputs=[txt_current_performer_id, img_performer_main, txt_performer_name, txt_performer_stashes, json_performer, gallery_performer_stash_images, state_peformer_stash, img_performer]
                            )
    btn_download_images_from_stash_box.click(download_images_from_stash_box, 
                                             inputs=[txt_current_performer_id], 
                                             outputs=[gallery_performer_stash_images, state_peformer_stash]
                                             )
    gallery_performer_stash_images.select(stash_image_selection, 
                                  inputs=[gallery_performer_stash_images, state_peformer_stash], 
                                  outputs=[img_performer, plot_analysis]
                                  )