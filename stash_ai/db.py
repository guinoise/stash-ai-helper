from utils.custom_logging import get_logger
logger= get_logger("stash_ai.db")
import gradio as gr
from typing import Union
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Engine
from stash_ai.config import config
import pathlib
import shutil
from time import sleep
import logging

database_file= pathlib.Path('stash-ai.sqlite3')

#logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

engine: Engine= None
lock_db= False
# def restore_backup(backup_filename: str) ->Union[None, str]:
#     global session, engine, lock_db
#     logger.warning("Restore of backup requested")
#     backup_file= config.encrypted_data.joinpath(backup_filename)
#     database_file_bk= database_file.parent.joinpath(f"{database_file.name}.bk")
#     if not backup_file.is_file():
#         logger.error(f"Backup file {backup_file.resolve()} NOT FOUND")
#         return False
#     error_message= None
#     try:
#         lock_db= True
#         if engine is not None:
#             logger.warning("Closing database")
#             engine.dispose(close=True)
#             engine= None
#             sleep(1)
#         if database_file_bk.exists():
#             database_file_bk.unlink()
#         logger.warning(f"Move current database to {database_file_bk.resolve()}")
#         shutil.move(str(database_file.resolve()), str(database_file_bk.resolve()))
#         logger.warning("Decrypting backup file")
#         pyAesCrypt.decryptFile(backup_file, database_file, config.aes_password)
#     except Exception as e:
#         error_message= f"Error restoring a copy of the database: {e!s}"
#         logger.error(error_message)
#         if not database_file.is_file() and database_file_bk.is_file():
#             logger.warning("Restoring old db from bk file")
#             shutil.copy(str(database_file_bk.resolve()), str(database_file.resolve()))
#     finally:
#         lock_db= False            
#     init_engine()
#     return error_message


# def backup_database(backup_file: str) ->bool:
#     global session, engine
#     initialized= engine is not None
#     backup_file= config.encrypted_data.joinpath(f"{backup_file}.aes")
#     if backup_file.exists():
#         return False
#     if initialized:
#         engine= None
#     success= False
#     try:
#         pyAesCrypt.encryptFile(database_file, backup_file, config.aes_password) 
#         success= True
#     except Exception as e:
#         logger.error("Error encrypting a copy of the database: %s", e)
#     if initialized:
#         init_engine()
#     return success

def init_engine():
    global engine
    if not gr.NO_RELOAD and engine is not None:
        logger.warning("Closing database on reload")
        close_db()
    if lock_db:
        raise ValueError('Database is locked, cannot open it')
    new_datababase= not database_file.is_file()
    if engine is None:
        logger.info('Init database: %s', database_file.resolve())
        url= f"sqlite+pysqlite:///{database_file.resolve()}"
        engine= create_engine(url=url)
        from stash_ai.model import BaseModel
        from alembic.config import Config
        from alembic import command
        from alembic.util import AutogenerateDiffsDetected, CommandError
        with engine.begin() as connection:
            try:
                alembic_cfg= Config(pathlib.Path('alembic.ini'), attributes={"no_logging": True})          
                alembic_cfg.set_main_option('sqlalchemy.url', url)
                alembic_cfg.attributes['connection']= connection
                if new_datababase:
                    logger.warning('Create database schema')
                    BaseModel.metadata.create_all(engine)
                    command.stamp(alembic_cfg, 'head')
                else:
                    logger.info('Check for database upgrade')            
                    command.upgrade(alembic_cfg, 'head')
                connection.commit()
            except:
                connection.rollback()
            finally:
                connection.close()

def get_engine() -> Engine:
    if engine is None:
        init_engine()
    return engine

def get_session() -> Session:
    if engine is None:
        init_engine()
    return Session(engine)

def close_db():
    global engine
    if engine is None:
        return
    engine.dispose()
    engine= None
    

