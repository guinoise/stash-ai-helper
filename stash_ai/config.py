from utils.custom_logging import get_logger
logger= get_logger('stash_ai.config')

import pathlib
from dataclasses import dataclass
import json
import gradio as gr
from stashapi.stashapp import StashInterface
from typing import Dict, List
from urllib.parse import urlunparse

@dataclass
class Config:
    stash_schema: str= 'http'
    stash_hostname: str= 'localhost'
    stash_port: int= 9999
    stash_api_key: str= None
    stash_base_url: str= None
    dev_mode: bool= False
    stash_interface: StashInterface= None
    stash_configuration: Dict= None
    stash_boxes: List= None
    data_dir: pathlib.Path= pathlib.Path(__file__).parent.parent.joinpath('local_assets')
    base_dir: pathlib.Path= pathlib.Path(__file__).parent.parent
config_file= pathlib.Path('config.json')
config= Config()


def connect_to_stash():
    logger.info("Connecting to stash")
    try:
        config.stash_base_url= urlunparse((config.stash_schema, f"{config.stash_hostname}:{config.stash_port}", "/", "", "", ""))
        logger.debug(f"connect_to_stash config.stash_base_url: {config.stash_base_url}")
        config.stash_interface = StashInterface({
            "scheme": config.stash_schema,
            "host": config.stash_hostname,
            "port": config.stash_port,
            "apikey": config.stash_api_key,
            "logger": logger
        })
        config.stash_configuration= config.stash_interface.get_configuration()
        gr.Info(f"Connected to stash", duration=1)  
        from utils.stashbox import init_stashboxes
        init_stashboxes()                             
    except Exception as e:
        config.stash_interface= None
        logger.error(f"Error connecting to stash : {e!s}")
        gr.Warning(f"Error connecting to stash 💥! : {e!s}", duration=10)

def load_config():
    logger.info("Loading configuration")
    conf= {}
    if config_file.is_file():
        try:
            with open(config_file, 'r') as file:
                conf= json.load(file)
            logger.info("Configuration loaded: %s", json.dumps(conf, indent=2))
        except Exception as e:
            logger.exception("Error loading config file")
    config.stash_schema= conf.get('stash_schema', 'http')
    config.stash_hostname= conf.get('stash_hostname', 'localhost')
    config.stash_port= conf.get('stash_port', 9999)
    config.stash_api_key= conf.get('stash_api_key', None)
    connect_to_stash()
    
def save_config():
    logger.info("Saving configuration")
    conf= {
        'stash_schema': config.stash_schema,
        'stash_hostname': config.stash_hostname,
        'stash_port': config.stash_port,
        'stash_api_key': config.stash_api_key
    }
    try:
        with open(config_file, 'w') as file:
            json.dump(conf, file, indent=2)
    except Exception as e:
        logger.exception("Error saving config file")
    logger.debug("Saved config: %r", conf)    
    connect_to_stash()

def save_config_btn_handler(stash_schema, stash_hostname, stash_port, stash_api_key):
    logger.info("Save config handler")
    config.stash_schema= stash_schema
    config.stash_hostname= stash_hostname
    config.stash_port= stash_port
    config.stash_api_key= stash_api_key
    save_config()
    return [config.stash_schema, config.stash_hostname, config.stash_port, stash_api_key]

def get_config_handler():
    return [config.stash_schema, config.stash_hostname, config.stash_port, config.stash_api_key]

def config_tab():
    with gr.Tab("Config") as tab_config:
        if config.dev_mode:
            html_dev= gr.HTML(value="<h1>Developer mode enabled</h1>")
        dd_stash_schema= gr.Dropdown(
            choices=['http', 'https'],
            type='value',
            label='Stash server schema',
            elem_id='stash_schema'
        )
        txt_stash_hostname= gr.Textbox(label='Stash server hostname')
        nb_stash_port= gr.Number(minimum=1, 
                                 maximum=65536, 
                                 step=1, 
                                 label='Stash server port', 
                                 elem_id='stash_port'
                                 )
        txt_stash_api_key= gr.Textbox(
            type='password',
            label='Stash server API key (empty for unsecure server)',
            elem_id='stash_api_key'
        )
        btn_save_config= gr.Button(value='Save config', variant='primary')
        btn_save_config.click(save_config_btn_handler, inputs=[dd_stash_schema, txt_stash_hostname, nb_stash_port, txt_stash_api_key], outputs=[dd_stash_schema, txt_stash_hostname, nb_stash_port, txt_stash_api_key])
        btn_reload_stash_config= gr.Button(value="Reload stash configuration", variant='huggingface')
        btn_reload_stash_config.click(connect_to_stash)
    tab_config.select(get_config_handler, None, outputs=[dd_stash_schema, txt_stash_hostname, nb_stash_port, txt_stash_api_key])

load_config()