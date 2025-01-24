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
    encrypted_data: pathlib.Path= pathlib.Path('encrypted_data') 
    aes_password: str= ''
    face_recognition_model: str= ''
    expand_face: float= 0
    face_identification_model: str= ''
    database_backend: str= 'sqlite3'
    database_endpoint: str= 'stash-ai.sqlite3'
   
config_file= pathlib.Path('config.json')
config= Config()

def refresh_backups_list():
    from stash_ai.db import list_backups    
    backups= list_backups()
    choices= ['-- MAKE A SELECTION --']
    logger.debug(f"refresh_backups_list {backups}")
    for index, name in backups:
        choices.append(name)
    logger.debug(f"refresh_backups_list {choices}")    
    return gr.Dropdown(choices=choices, value=choices[0], type='index')

def backup_button_handler(backup_name: str):
    from stash_ai.db import backup_database
    if not backup_name or '.' in backup_name:
        raise gr.Error(f'Backup name {backup_name} must not contain . (dot) character')       
    # if not backup_name.endswith('.sqlite3'):
    #     raise gr.Error(f'Backup name {backup_name} must end with .sqlite3')
    if backup_database(backup_name=backup_name):
        gr.Info('Backup completed')
    else:
        gr.Warning('Backup failed')
    return refresh_backups_list()

def restore_backup_button_handler(backup_index: int):
    from stash_ai.db import restore_database_backup, list_backups
    logger.debug(f"restore_backup_button_handler value: {backup_index} ({type(backup_index)}")
    if not backup_index:
        raise gr.Error('Select a backup file')
    backup_name= list_backups()[backup_index-1][0]
    gr.Warning(f"Restoring {backup_name}")
    err_message= restore_database_backup(backup_name=backup_name)
    if  err_message is None:
        gr.Warning('Restore complete')
    else:
        raise gr.Error(f'Restore failed: {err_message}') 

def connect_to_stash():
    logger.info("Connecting to stash")
    try:
        config.stash_base_url= urlunparse((config.stash_schema, f"{config.stash_hostname}:{config.stash_port}", "", "", "", ""))
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
    config.aes_password= conf.get('aes_password', '')   
    config.face_recognition_model= conf.get('face_recognition_model', 'ssd')   
    config.face_identification_model= conf.get('face_identification_model', 'VGG-Face')   
    config.expand_face= conf.get('expand_face', 30)   
    config.database_backend= conf.get('database_backend', 'sqlite3')   
    config.database_endpoint= conf.get('database_endpoint', 'stash-ai.sqlite3')    
    connect_to_stash()
    
def save_config():
    logger.info("Saving configuration")
    conf= {
        'stash_schema': config.stash_schema,
        'stash_hostname': config.stash_hostname,
        'stash_port': config.stash_port,
        'stash_api_key': config.stash_api_key,
        'aes_password': config.aes_password,
        'face_recognition_model': config.face_recognition_model,
        'face_identification_model': config.face_identification_model,
        'expand_face': config.expand_face,
        'database_backend': config.database_backend,
        'database_endpoint': config.database_endpoint
    }
    try:
        with open(config_file, 'w') as file:
            json.dump(conf, file, indent=2)
    except Exception as e:
        logger.exception("Error saving config file")
    logger.debug("Saved config: %r", conf)    
    connect_to_stash()

def save_config_btn_handler(stash_schema, 
                            stash_hostname, 
                            stash_port, 
                            stash_api_key, 
                            aes_password, 
                            face_identification_model, 
                            face_recognition_model, 
                            face_expand,
                            db_backend,
                            db_endpoint):
    logger.info("Save config handler")
    config.stash_schema= stash_schema
    config.stash_hostname= stash_hostname
    config.stash_port= stash_port
    config.stash_api_key= stash_api_key
    config.aes_password= aes_password
    config.face_identification_model= face_identification_model
    config.face_recognition_model= face_recognition_model
    config.expand_face= face_expand
    config.database_backend= db_backend
    config.database_endpoint= db_endpoint
    save_config()
    return [config.stash_schema, 
            config.stash_hostname,
            config.stash_port,
            config.stash_api_key, 
            config.aes_password,
            config.face_identification_model,
            config.face_recognition_model,
            config.expand_face,
            config.database_backend,
            config.database_endpoint]

def get_config_handler():
    return [config.stash_schema, 
            config.stash_hostname, 
            config.stash_port, 
            config.stash_api_key, 
            config.aes_password, 
            config.face_identification_model, 
            config.face_recognition_model, 
            config.expand_face,
            config.database_backend,
            config.database_endpoint]

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
        with gr.Group():
            txt_aes_password= gr.Textbox(
                type='password',
                label='AES file encryption password',
                elem_id='aes_password'
            )
            chk_show= gr.Checkbox(value=False, label="Show password") 
        with gr.Group():
            dd_db_backend= gr.Dropdown(choices=["sqlite3", "postgresql"], value=config.database_backend)
            txt_db_endpoint= gr.Text(label='Database endpoint', info="For sqlite3, name of the file. For postgresql USER:PASSWORD@host/DB", value=config.database_endpoint)
        with gr.Group():
            dd_face_recognition_model= gr.Dropdown(choices=["retinaface", "mediapipe", "mtcnn", "dlib", "ssd", "opencv"])
            number_face_expand= gr.Number(label= "Expand % face detection")
            dd_face_identification_model= gr.Dropdown(choices=["VGG-Face", "Facenet", "OpenFace", "DeepID", "Dlib", "ArcFace"])
        btn_save_config= gr.Button(value='Save config', variant='primary')
        btn_reload_stash_config= gr.Button(value="Reload stash configuration", variant='huggingface')
        with gr.Group():
            txt_filename= gr.Textbox(value='', label='Backup database', info='Backup name (no dots)')
            btn_backup= gr.Button(value='Backup', variant='primary')
        with gr.Accordion("Restore database", open=False):
            with gr.Group():
                with gr.Row():
#                    dd_db_backups= gr.Dropdown(choices=['-- NOT LOADED --'], label='Database backups', type='index', value=0)
                    dd_db_backups= refresh_backups_list()
                    dd_db_backups.label='Database backups'
                    btn_refresh_backups= gr.Button(value='🔄', elem_classes="tool")
                with gr.Row():
                    btn_restore_backup= gr.Button(value='Restore backup', variant='stop')
    def set_password_visibility(visible):
        if visible:
            type='text'
        else:
            type='password'
        return gr.Textbox(type=type)
    tab_config.select(get_config_handler, 
                      None, 
                      outputs=[dd_stash_schema, 
                               txt_stash_hostname, 
                               nb_stash_port,
                               txt_stash_api_key,
                               txt_aes_password,
                               dd_face_identification_model,
                               dd_face_recognition_model,
                               number_face_expand,
                               dd_db_backend,
                               txt_db_endpoint])
    btn_save_config.click(save_config_btn_handler, 
                          inputs=[dd_stash_schema, 
                                  txt_stash_hostname,
                                  nb_stash_port,
                                  txt_stash_api_key,
                                  txt_aes_password,
                                  dd_face_identification_model,
                                  dd_face_recognition_model,
                                  number_face_expand,
                                  dd_db_backend,
                                  txt_db_endpoint],
                          outputs=[dd_stash_schema, 
                                   txt_stash_hostname,
                                   nb_stash_port,
                                   txt_stash_api_key,
                                   txt_aes_password,
                                   dd_face_identification_model,
                                   dd_face_recognition_model,
                                   number_face_expand,
                                   dd_db_backend,
                                   txt_db_endpoint])
    btn_reload_stash_config.click(connect_to_stash)
    btn_backup.click(backup_button_handler, txt_filename, dd_db_backups)
    chk_show.change(set_password_visibility, [chk_show], [txt_aes_password])
    btn_refresh_backups.click(refresh_backups_list, None, [dd_db_backups])
    btn_restore_backup.click(restore_backup_button_handler, dd_db_backups, None)