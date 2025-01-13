from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_scenes")

import gradio as gr
from stash_ai.config import config
from stash_ai.db import get_session
from stash_ai.model import StashBox, Performer, PerformerStashBoxImage


def stash_scene_tab():
    state_search_scene= gr.BrowserState([])
    state_scene_stash= gr.BrowserState({"scene_ids": [], "current_index": None})
    with gr.Tab("Scenes") as scene_tab:
        pass
        # with gr.Tabs() as main_tab_scene:
        #     with gr.TabItem("Scene", id=20):
        #         with gr.Row():
        #             with gr.Column():
        #                 with gr.Group():
        #                     with gr.Row():
        #                         txt_scene_id= gr.Number(label='Scene id', precision=0)
        #                         btn_load_scene_id= gr.Button(value='🔄', elem_classes="tool", min_width=10)
