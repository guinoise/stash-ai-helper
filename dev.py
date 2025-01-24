from utils.custom_logging import setup_logging, setup_std_logging, setup_rich_logging, get_logger
setup_rich_logging()
logger= get_logger('dev')
import os
import gradio as gr
from stash_ai.config import config, config_tab, load_config
from stash_ai.db import init_engine
from stash_ai.dev import dev_tab
from stash_ai.stash_performers import stash_performers_tab
from stash_ai.stash_scenes import stash_scene_tab
from stash_ai.db import init_engine
import os

load_config()
init_engine()
css = ""
logger.info("Setting GRADIO_ALLOWED_PATHS")
if os.environ.get('GRADIO_ALLOWED_PATHS') is None:
    allowed_paths= []
else:
    allowed_paths= os.environ.get('GRADIO_ALLOWED_PATHS').split(',')
logger.info(f"Allowed_paths before: {allowed_paths}")
if str(config.data_dir.resolve()) not in allowed_paths:
    allowed_paths.append(str(config.data_dir.resolve()))
os.environ['GRADIO_ALLOWED_PATHS']= ','.join(allowed_paths)
logger.info(f"GRADIO_ALLOWED_PATHS: {os.environ.get('GRADIO_ALLOWED_PATHS')}")

if os.path.exists("./style.css"):
    with open(os.path.join("./style.css"), "r", encoding="utf8") as file:
        logger.info("Load CSS...")
        css += file.read() + "\n"

if os.path.exists("./README.md"):
    with open(os.path.join("./README.md"), "r", encoding="utf8") as file:
        README = file.read()
        
config.dev_mode= True
with gr.Blocks(css=css, title="Stash AI", theme=gr.themes.Default()) as demo:
    with gr.Tabs(elem_id="main_tabs"):
        stash_scene_tab()
        stash_performers_tab()
        with gr.Tab("Readme"):
            gr.Markdown(README)
        config_tab()
        dev_tab()

def unloading():
    logger.warning("DEMO UNLOADING")
    
demo.unload(unloading)

if __name__ == "__main__":
    demo.launch()