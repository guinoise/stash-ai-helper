from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_performers")

from typing import List, Dict
import gradio as gr
from stash_ai.config import config
from stash_ai.model import StashBox, Performer
from stash_ai.db import get_session
from utils.image import download_performer_image

def search_performer_by_name(txt_performer_name):
    logger.info(f"Perform search on stash for name {txt_performer_name}")
    
    performers= None
    performers_images= []
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
                performer: Performer= session.get(Performer, performer_data.get('id'))
                if performer is None:
                    performer= Performer(id= performer_data.get('id'), name=performer_data.get('name'))
                    session.add(performer)
                img= download_performer_image(performer_data.get('image_path'), performer=performer)
                if img is None:
                    logger.error(f"Error img is none {performer.id}")
                else:
                    performers_images.append((img, performer.name))
            session.commit()
    else:
        gr.Warning("Could not perform a full search.", duration=2)
    
        
    return [performers_images,performers]

def performer_gallery_select(selection, evt: gr.SelectData):
    logger.info(f"Performer gallery selection : {selection} {evt!r}")
    logger.info(f"You selected {evt.value} at {evt.index} from {evt.target}")
    logger.info(f"{type(evt.value.get('image'))}")
    
def stash_performers_tab():
    with gr.Tab("Performers") as performers_tab:
        with gr.Tab("Search"):
            with gr.Row():
                with gr.Column():
                    with gr.Group():
                        with gr.Row():
                            txt_performer_name= gr.Textbox(label='Performer name')
                            btn_search_performer_name= gr.Button(value='🔎', elem_classes="tool", min_width=10)

            with gr.Row(visible=config.dev_mode):
                with gr.Accordion(label="Dev", open=False):
                    performers_results= gr.Json(label="Performers results")
            with gr.Row():
                with gr.Column():
                    performer_gallery= gr.Gallery(label='Performers', allow_preview=False, object_fit='contain', height="90vh")
        with gr.Tab("Performer"):
            with gr.Row():
                with gr.Column():
                    with gr.Group():
                        with gr.Row():
                            txt_performer_id= gr.Number(label='Performer id', precision=0)
                            btn_search_performer_id= gr.Button(value='🔎', elem_classes="tool", min_width=10)
    btn_search_performer_name.click(search_performer_by_name, inputs=[txt_performer_name], outputs=[performer_gallery, performers_results])
    txt_performer_name.submit(search_performer_by_name, inputs=[txt_performer_name], outputs=[performer_gallery, performers_results])
    performer_gallery.select(performer_gallery_select, performer_gallery, None)