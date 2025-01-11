from utils.custom_logging import get_logger
logger= get_logger("stash_ai.dev")

from typing import List, Dict
import gradio as gr
from stash_ai.config import config
from stash_ai.model import StashBox


def dev_tab():
    with gr.Tab("Developper") as tab_dev:
        with gr.Column():
            with gr.Accordion("Stash complete configuration", open=False):
                gr.Json(label='Stash configuration', value=config.stash_configuration)
            with gr.Row():
                with gr.Accordion("Stash boxes raw", open=False):
                    gr.Json(label='Stash boxes configuration', value=(config.stash_configuration.get('general', {}).get('stashBoxes', []) if config.stash_configuration is not None else None))

