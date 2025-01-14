import gradio as gr
from utils.custom_logging import setup_logging, setup_std_logging, setup_rich_logging, get_logger
logger= get_logger('gui')
#logger= setup_std_logging()
import argparse
import os
from stash_ai.config import config, config_tab, load_config
from stash_ai.dev import dev_tab
from stash_ai.stash_performers import stash_performers_tab
from stash_ai.stash_scenes import stash_scene_tab
from stash_ai.db import init_engine
       
def UI(*args, **kwargs):
    load_config()
    config.dev_mode= False
    css = ""

    if os.path.exists("./style.css"):
        with open(os.path.join("./style.css"), "r", encoding="utf8") as file:
            logger.info("Load CSS...")
            css += file.read() + "\n"

    if os.path.exists("./README.md"):
        with open(os.path.join("./README.md"), "r", encoding="utf8") as file:
            README = file.read()
            
    interface= gr.Blocks(
        css=css,
        title="Stash AI",
        theme=gr.themes.Default()
    )
    init_engine()

    with interface:
        with gr.Tabs(elem_id="main_tabs"):
            #stash_scene_tab()
            with gr.Tab("Readme"):
                gr.Markdown(README)
            stash_performers_tab()
            config_tab()
            #dev_tab()

    # Show the interface
    launch_kwargs = {}
    server_port = kwargs.get("server_port", 0)
    inbrowser = kwargs.get("inbrowser", False)
    share = kwargs.get("share", False)
    server_name = kwargs.get("listen")

    launch_kwargs["server_name"] = server_name
    if server_port > 0:
        launch_kwargs["server_port"] = server_port
    if inbrowser:
        launch_kwargs["inbrowser"] = inbrowser
    if share:
        launch_kwargs["share"] = share
    interface.launch(**launch_kwargs)

if __name__ == "__main__":
    # torch.cuda.set_per_process_memory_fraction(0.48)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--listen",
        type=str,
        default="127.0.0.1",
        help="IP to listen on for connections to Gradio",
    )
    parser.add_argument(
        "--server_port",
        type=int,
        default=7870,
        help="Port to run the server listener on, default 7870",
    )
    parser.add_argument("--inbrowser", action="store_true", help="Open in browser")
    parser.add_argument(
        "--headless", action="store_true", help="Is the server headless"
    )
    args = parser.parse_args()

    UI(
        inbrowser=args.inbrowser,
        server_port=args.server_port,
        listen=args.listen,
    )
