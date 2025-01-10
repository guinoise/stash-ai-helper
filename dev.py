from utils.custom_logging import setup_logging, setup_std_logging, setup_rich_logging, get_logger
setup_rich_logging()
logger= get_logger('dev')
import os
import gradio as gr
from stash_ai.config import config, config_tab
from stash_ai.db import get_session, init_engine
from stash_ai.dev import dev_tab
from stash_ai.stash_performers import stash_performers_tab

css = ""

if os.path.exists("./style.css"):
    with open(os.path.join("./style.css"), "r", encoding="utf8") as file:
        logger.info("Load CSS...")
        css += file.read() + "\n"

if os.path.exists("./README.md"):
    with open(os.path.join("./README.md"), "r", encoding="utf8") as file:
        README = file.read()
        
init_engine()

with gr.Blocks(css=css, title="Stash AI", theme=gr.themes.Default()) as demo:
    with gr.Tab("Readme"):
        gr.Markdown(README)
    stash_performers_tab()
    config_tab(dev_mode=True)
    dev_tab()

if __name__ == "__main__":
    demo.launch()