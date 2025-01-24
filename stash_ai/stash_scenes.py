from utils.custom_logging import get_logger
logger= get_logger("stash_ai.stash_scenes", True)

import gradio as gr
if gr.NO_RELOAD:
    from deepface import DeepFace
from stash_ai.config import config
from stash_ai.db import get_session
from stash_ai.model import Performer, Scene, Img, ImgFile, ImageAnalysis, DeepfaceFace, FaceStatus
from utils.performer import get_performer_stash_image, load_performer, get_unknown_performer_image
from utils.scene import load_scene, create_or_update_scene_from_stash, extract_scene_images, decord_scene
from utils.image import image_analysis, get_annotated_image_analysis_path, get_face_image_path, get_face_phash, hashes_are_similar, group_faces, load_image_analysis_from_imgFiles
from datetime import timedelta
import random
from PIL import Image
from tqdm import tqdm 
from typing import List, Dict
import pandas as pd
import pathlib

#assign_confirm, inputs=[state_scene_stash, txt_group_name, txt_perf_id], outputs=[state_scene_stash]
def assign_confirm(state_scene_stash, group_name, performer_id):
    logger.info(f"Assign confirm performer {performer_id} to group {group_name}")
    with get_session() as session:
        performer= session.get(Performer, performer_id)
        if performer is None:
            return state_scene_stash
        logger.debug(f"Performer {performer}")
        for face_id in state_scene_stash['groups'].get(group_name):
            face: DeepfaceFace= session.get(DeepfaceFace, face_id)
            face.performer= performer
            face.status= FaceStatus.CONFIRMED
            session.add(face)
        session.commit()
        state_scene_stash.get('group_results', {}).get(group_name, {})['confirmed_id']= performer_id
    return state_scene_stash

def change_group_name(old_name, new_name, state_scene_stash): 
    logger.info(f"Change group name from {old_name} to {new_name}")
    with get_session() as session:
        faces_list= state_scene_stash['groups'].pop(old_name, [])
        if new_name in state_scene_stash['groups'].keys():
            state_scene_stash['groups'][new_name]+= faces_list
        else:
            state_scene_stash['groups'][new_name]= faces_list
        
        for face_id in faces_list:
            face= session.get(DeepfaceFace, face_id)
            if face is None:
                continue
            face.group= new_name
            session.add(face)
        session.commit()
    return state_scene_stash


def update_face(face_id: int, face_status: str, face_group: str, state_scene_stash):
    logger.warning(f"update_face_status FaceId: {face_id} Status: {face_status} {FaceStatus(face_status)} Group: {face_group}")
    with get_session() as session:
        face= session.get(DeepfaceFace, face_id)
        face.status= FaceStatus(face_status)
        if face.group != face_group:
            if face.group:
                state_scene_stash['groups'][face.group].remove(face.id)
            else:
                state_scene_stash['ungrouped'].remove(face.id)
            if face_group:
                if face_group not in state_scene_stash['groups'].keys():
                    state_scene_stash['groups'][face_group]= [face.id]
                else:
                    state_scene_stash['groups'][face_group].append(face.id)        
            face.group= face_group
        session.add(face)
        session.commit()
    return state_scene_stash

#inputs=[state_scene_stash, number_deepface_ident_face_conf, number_ident_hash_tolerance, number_limit_ident],
def handler_group_faces(state_scene_stash, number_deepface_ident_face_conf, number_ident_hash_tolerance, progress=gr.Progress(track_tqdm=True)):
    logger.info(f"handler_group_faces detector {config.face_identification_model} expand {config.expand_face} min_confidence face {number_deepface_ident_face_conf} hash tolerance {number_ident_hash_tolerance} model {config.face_identification_model}")
    logger.debug(f"handler_group_faces {state_scene_stash}")
    html= ""  
    state_scene_stash['discarded']=[]
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        faces: List[DeepfaceFace]= []
        faces_hashes= []
        img: Img            
        for img in progress.tqdm(scene.images, desc='Retrieving faces...', unit='image', total=len(scene.images)):
            logger.debug(f"detect_and_extract_faces Detection on {img}")
            if not img.original_file_exists():
                logger.warning(f"detect_and_extract_faces File not on disk : {img}")
                continue
            analysis: ImageAnalysis= image_analysis(img.original_file(), config.face_recognition_model, config.expand_face, session)

            face: DeepfaceFace
            for face in analysis.faces:
                if face.overlapping:
                    face.status= FaceStatus.AUTO_DISCARD
                    session.add(face)
                    continue
                if face.status == FaceStatus.DISCARD:
                    state_scene_stash['discarded'].append(face.id)
                    continue    
                if face.status == FaceStatus.AUTO_DISCARD:
                    continue
                hash= get_face_phash(face)
                if face.confidence < number_deepface_ident_face_conf:
                    face.status= FaceStatus.AUTO_DISCARD
                    session.add(face)
                    continue
                for oh in faces_hashes:
                    if hashes_are_similar(hash, oh, number_ident_hash_tolerance):
                        face.status= FaceStatus.AUTO_DISCARD
                        session.add(face)
                        break
                else:
                    faces.append(face)
                faces_hashes.append(hash)
        
        groups= group_faces(f"Scene {scene.id}", faces, detector_backend=config.face_recognition_model, expand_percentage=config.expand_face, model_name=config.face_identification_model, session=session)
        state_scene_stash['groups']= {}
        state_scene_stash['ungrouped']= []
        for groupe_name, faces in groups.items():
            for face in faces:
                if groupe_name not in state_scene_stash['groups'].keys():
                    state_scene_stash['groups'][groupe_name]= [face.id]
                else:
                    state_scene_stash['groups'][groupe_name].append(face.id)
        face: DeepfaceFace
        session.commit()
    return [state_scene_stash, "Extract and group"]

                        # inputs=[state_scene_stash, number_deepface_ident_face_conf, number_ident_hash_tolerance],
                        # outputs=[state_scene_stash, html_ident_result]
    
def ident_faces(state_scene_stash, number_deepface_ident_face_conf, number_ident_hash_tolerance, progress=gr.Progress(track_tqdm=True)):
    logger.info(f"ident_faces detector {config.face_recognition_model} min_confidence face {number_deepface_ident_face_conf} hash tolerance {number_ident_hash_tolerance} model {config.face_identification_model}")
    logger.debug(f"ident_faces {state_scene_stash}")
    dataset_dir= config.data_dir.joinpath('dataset/performers')
    if not dataset_dir.exists():
        gr.Warning("Dataset directory does not exists, prepare a dataset from performer batch operations.")
        return None, None, None
    with get_session() as session:
        state_scene_stash['groups_results']= {}
        for group_name, faces_list in progress.tqdm(state_scene_stash.get('groups', {}).items(), desc='Groups', unit='group'):
            logger.info(f"Group {group_name}")
            frames_results= []
            for face_id in progress.tqdm(faces_list, desc='Identify...', unit='face'):
                face: DeepfaceFace= session.get(DeepfaceFace, face_id)
                df= DeepFace.find(get_face_image_path(face), db_path=dataset_dir.resolve(), detector_backend=config.face_recognition_model, model_name=config.face_identification_model, enforce_detection=False)
                frames_results.append(df[0])
            df= pd.concat(frames_results)
            perf_ids= []
            perf_names= []
            for path in df.identity:
                match_face_id= int(pathlib.Path(path).stem.split("_")[0])
                match_face: DeepfaceFace= session.get(DeepfaceFace, match_face_id)
                if match_face is None or match_face.performer is None:
                    perf_ids.append(None)
                    perf_names.append(None)
                else:
                    perf_ids.append(match_face.performer.id)
                    perf_names.append(match_face.performer.name)
            df['PerformerId'] = perf_ids
            df['PerformerName'] = perf_names
            df['score']= ((df.groupby('PerformerId')['PerformerId'].transform('size')/len(df))+1) * df.groupby('PerformerId')['threshold'].transform('max')
            s= df.groupby('PerformerId').agg("max").sort_values('score', ascending=False).head(3)
            s.reset_index()
            state_scene_stash['groups_results'][group_name]= []
            for performer_id, row in s.iterrows():
                state_scene_stash['groups_results'][group_name].append({'performer_id': performer_id, 'performer_name': row['PerformerName'], 'score': round(row['score'],3)})                
    return state_scene_stash, "Identification of group completed"

def render_detect_extract_faces(state_scene_stash, min_confidence, dryrun, hash_tolerance, number_of_samples, progress=gr.Progress(track_tqdm=True)):
    logger.info(f"render_detect_extract_faces state {state_scene_stash}, detector {config.face_recognition_model} expand {config.expand_face} min_confidence {min_confidence} dryrun {dryrun} nb samples {number_of_samples}, hash tolerance {hash_tolerance}")

    # if state_scene_stash.get('scene_id') is None:
    #     gr.Warning("Current scene id not found. Reload the scene.")
    #     return
    # with get_session() as session:
    #     scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
    #     if scene is None:
    #         raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
    #     imgs: List[Img]= []
    #     if dryrun:
    #         imgs= random.choices(scene.images, k=min(len(scene.images), number_of_samples))
    #     else:
    #         imgs= scene.images

    #     img: Img            
    #     for img in tqdm(imgs, desc='Processing...', unit='image'):
    #         logger.debug(f"detect_and_extract_faces Detection on {img}")
    #         if not img.original_file_exists():
    #             logger.warning(f"detect_and_extract_faces File not on disk : {img}")
    #             continue
    #         analysis: ImageAnalysis= image_analysis(img.original_file(), config.face_recognition_model, config.expand_face, session)
    #         gallery_face_dection.append(img.original_file().get_image_path())
    #         gallery_face_dection.append(get_annotated_image_analysis_path(analysis, number_deepface_min_confidence))

    #         face: DeepfaceFace
    #         for face in analysis.faces:
    #             if face.overlapping:
    #                 continue
    #             hash= get_face_phash(face)
    #             for oh in faces_hashes:
    #                 if hashes_are_similar(hash, oh, number_hash_tolerance):
    #                     break
    #             else:
    #                 gallery_unique_faces.append((get_face_image_path(face), f"[{face.confidence}] {face.race} ({int(face.race_confidence)}) {face.gender} ({int(face.gender_confidence)}) {face.age} yo"))
    #             faces_hashes.append(hash)
    #             gallery_sample_faces.append((get_face_image_path(face), f"[{face.confidence}] {face.race} ({int(face.race_confidence)}) {face.gender} ({int(face.gender_confidence)}) {face.age} yo"))                
    #     session.commit()

    pass

def detect_and_extract_faces(state_scene_stash, number_deepface_min_confidence, checkbox_dryrun_face_detection, number_hash_tolerance, number_of_samples, progress=gr.Progress(track_tqdm=True)):
    logger.info(f"detect_and_extract_faces state {state_scene_stash}, detector {config.face_recognition_model} expand {config.expand_face} min_confidence {number_deepface_min_confidence} dryrun {checkbox_dryrun_face_detection} nb samples {number_of_samples}, hash tolerance {number_hash_tolerance}")
    # results= analyse_extracted_video(radio_deepface_detector, number_deepface_extends, checkbox_dryrun_face_detection, progress)
    # logger.debug(f"detect_and_extract_faces {results}")
    gallery_face_dection= []
    gallery_sample_faces= []
    gallery_unique_faces= []
    faces_hashes= []
    infos_html= ""
    if state_scene_stash.get('scene_id') is None:
        gr.Warning("Current scene id not found. Reload the scene.")
        return [gallery_face_dection, gallery_sample_faces, gallery_unique_faces, infos_html]
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        imgs: List[Img]= []
        if checkbox_dryrun_face_detection:
            imgs= random.choices(scene.images, k=min(len(scene.images), number_of_samples))
        else:
            imgs= scene.images

        img: Img            
        for img in tqdm(imgs, desc='Processing...', unit='image'):
            logger.debug(f"detect_and_extract_faces Detection on {img}")
            if not img.original_file_exists():
                logger.warning(f"detect_and_extract_faces File not on disk : {img}")
                continue
            analysis: ImageAnalysis= image_analysis(img.original_file(), config.face_recognition_model, config.expand_face, session)
            gallery_face_dection.append(img.original_file().get_image_path())
            gallery_face_dection.append(get_annotated_image_analysis_path(analysis, number_deepface_min_confidence))

            face: DeepfaceFace
            for face in analysis.faces:
                if face.overlapping or face.status in [FaceStatus.DISCARD, FaceStatus.AUTO_DISCARD]:
                    continue
                hash= get_face_phash(face)
                for oh in faces_hashes:
                    if hashes_are_similar(hash, oh, number_hash_tolerance):
                        face.status= FaceStatus.AUTO_DISCARD
                        session.add(face)
                        break
                else:
                    gallery_unique_faces.append((get_face_image_path(face), f"[{face.confidence}] {face.race} ({int(face.race_confidence)}) {face.gender} ({int(face.gender_confidence)}) {face.age} yo"))
                faces_hashes.append(hash)
                gallery_sample_faces.append((get_face_image_path(face), f"[{face.confidence}] {face.race} ({int(face.race_confidence)}) {face.gender} ({int(face.gender_confidence)}) {face.age} yo"))                
        session.commit()
        infos_html+= f"""
            <p>Images analyzed : {len(imgs)}</p>
            <p>Faces extracted : {len(gallery_sample_faces)}</p>
            <p>Unique faces : {len(gallery_unique_faces)}</p>
        """
    # metadata: ImageAnalysis
    # for metadata in results:
    #     if not metadata.sample:
    #         continue
    #     gallery_face_dection.append(metadata.get_numpy())
    #     gallery_face_dection.append(metadata.get_numpy_with_overlay(number_deepface_min_confidence))
    #     #gallery_sample_faces.extend(metadata.get_faces_numpy(number_deepface_min_confidence))
    # logger.info(f"analyse_extracted_video : Gallery faces : {len(gallery_face_dection)} Sample faces: {len(gallery_sample_faces)}")
    return [gallery_face_dection, gallery_sample_faces, gallery_unique_faces, infos_html]
    #outputs=[gallery_face_dection, gallery_sample_faces, gallery_unique_faces]

def handle_load_samples(number_of_samples, state_scene_stash):
    logger.info(f"extract_images Samples {number_of_samples} state {state_scene_stash}")
    imgs= []
    if state_scene_stash.get('scene_id') is None:
        gr.Warning("Current scene id not found. Reload the scene.")
        return [None, state_scene_stash]
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        if len(scene.images) > 0:
            img: Img
            for img in random.choices(scene.images, k=min(len(scene.images), number_of_samples)):
                if img.original_file_exists():
                    imgs.append(img.original_file().get_image_path())
    return [imgs, state_scene_stash]   

     
#inputs=[number_of_samples, state_scene_stash],
def extract_images(number_hash_tolerance, state_scene_stash, progress= gr.Progress(track_tqdm=True)):
    logger.info(f"extract_images Hash tolerance {number_hash_tolerance} state {state_scene_stash}")
    nb_images= 0
    if state_scene_stash.get('scene_id') is None:
        gr.Warning("Current scene id not found. Reload the scene.")
        return [0, state_scene_stash]
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        if scene is None:
            raise gr.Error(f"Scene {state_scene_stash.get('scene_id')} not found in DB!")
        extract_scene_images(scene, hash_tolerance=number_hash_tolerance, session=session)
        nb_images= scene.nb_images
        #decord_scene(scene, hash_tolerance=number_hash_tolerance, downscale=number_downscale, session=session)
        session.commit()
           
    # nb_images= math.ceil(number_duration * number_extract_images_per_seconds)
    # logger.info(f"extract_images URL: {text_video_url} Img per second : {number_extract_images_per_seconds} FPS: {number_frames_per_second} Total images: {nb_images} Samples: {number_of_samples}")
    # return extract_video_images(text_video_url, number_duration, number_frames_per_second, number_extract_images_per_seconds, number_of_samples, progress)
    return [nb_images, state_scene_stash]
    #outputs=[gallery_extracted, number_of_images, state_scene_stash]


def update_scene_infos(state_scene_stash):
    logger.info(f"update_scene_infos : {state_scene_stash.get('scene_id')}")
    nb_images= 0
    with get_session() as session:
        scene: Scene= load_scene(state_scene_stash.get('scene_id'), session)
        performers_images= []
        html= ""
        if scene:
            html= f"""
            <h1>{scene.title}</h1>
            <p>{scene.details}</p>
            <p>
                <h2>Media information</h2>
                <ul>
                    <li>File {scene.local_file_name}</li>
                    <li>Codec {scene.video_codec}</li>
                    <li>Size {scene.width}x{scene.height}</li>
                    <li>Duration {scene.duration} seconds</li>
                    <li>FPS {scene.fps}</li>
                    <li>{scene.number_of_frames()} frames</li>
                </ul>
            </p>
            """
            nb_images= scene.nb_images
            if scene.nb_images:
                html += f"""
                <p>
                    <h2>Extraction information</h2>
                    <ul>
                        <li>Number of image extracted {scene.nb_images}</li>
                        <li>Hash tolerance during extraction {scene.hash_tolerance}</li>
                        <li>Extraction duration : {str(timedelta(seconds=scene.extraction_time)) if scene.extraction_time is not None else ''}
                    </ul>
                </p>
                """

            # if scene.downscale is not None:
            #     html += f"""
            #     <p>
            #         <h2>Extraction information</h2>
            #         <ul>
            #             <li>Downscaled extraction {scene.downscale}</li>
            #             <li>Dowscaled size {scene.downscale_width}x{scene.downscale_height}</li>
            #             <li>Number of image extracted {scene.nb_images}</li>
            #             <li>Hash tolerance during extraction {scene.hash_tolerance}</li>
            #             <li>Extraction duration : {str(timedelta(seconds=scene.extraction_time)) if scene.extraction_time is not None else ''}
            #         </ul>
            #     </p>
            #     """

            html+= f"""
            <p><a href="{scene.get_url()}" target="_blank">{scene.get_url()}</a>            
            """
            
            performer: Performer
            logger.debug(f"update_scene_infos Performers: {scene.performers}")
            for performer in scene.performers:
                performer_img= get_performer_stash_image(performer, session=session)
                performer_text= f"{performer.name} [{performer.id}]"                
                if performer_img is None:
                    performer_img= get_unknown_performer_image()
                performers_images.append((performer_img, performer_text))
            imgFiles: List[ImgFile]= []
            for img in scene.images:
                if img.original_file_exists():
                    imgFiles.append(img.original_file())
            state_scene_stash['groups']= {}
            state_scene_stash['ungrouped']= []            
            state_scene_stash['discarded']= []
            analysis: ImageAnalysis
            analysis_list= load_image_analysis_from_imgFiles(imgFiles, config.face_recognition_model, config.expand_face, session)
            for analysis in analysis_list:
                face: DeepFace
                for face in analysis.faces:
                    if face.overlapping or face.status == FaceStatus.AUTO_DISCARD:
                        continue
                    if face.status == FaceStatus.DISCARD:
                        state_scene_stash['discarded'].append(face.id)
                        continue
                    if not face.group:
                       state_scene_stash['ungrouped'].append(face.id)
                    elif face.group not in state_scene_stash['groups'].keys():
                        state_scene_stash['groups'][face.group]= [face.id]
                    else:
                        state_scene_stash['groups'][face.group].append(face.id)
                        
        session.commit()
    return [html, performers_images, state_scene_stash, nb_images]
    # outputs=[html_scene_infos, gallery_performers, state_scene_stash]
    
def handler_load_scene(scene_id, state_scene_stash):
    logger.info(f"handler_load_scene : {scene_id}")
    with get_session() as session:
        scene: Scene= create_or_update_scene_from_stash(scene_id, None, session)
        state_scene_stash["scene_id"]= scene.id if scene is not None else None
        session.commit()
    logger.debug(f"handler_load_scene out state : {state_scene_stash}")
    return state_scene_stash

    # outputs=[html_scene_infos, gallery_performers, state_scene_stash]


def stash_scene_tab():
    with gr.Tab("Scenes", id="scene_main_tab") as scene_tab:
        state_scene_stash= gr.BrowserState({"scene_id": None})
        with gr.Tabs(elem_id="scenes_tabs") as scenes_tabs:
            with gr.TabItem("Scene", id="scene_stash_tab"):
                with gr.Row():
                    with gr.Column():
                        with gr.Row():
                            txt_scene_id= gr.Number(label='Scene id', precision=0)
                            btn_load_scene_id= gr.Button(value='🔄', elem_classes="tool", min_width=10)
                        with gr.Row():
                            with gr.Group():
                                html_scene_infos= gr.HTML(label='Scene details', value='')
                        with gr.Row():
                            gallery_performers= gr.Gallery(interactive=False, object_fit='scale-down', height="15vh", label="Performers", columns=10)                       
                        with gr.Tabs():
                            with gr.Tab('Extraction'):
                                with gr.Row():
                                    with gr.Column(scale=4):
                                        with gr.Row():
                                            number_hash_tolerance= gr.Number(label='Hash tolerance', info='Higher number for less images', precision=0, value=20)
                                        btn_extract_images= gr.Button(value='Extract images', variant='stop')
                                    with gr.Column():
                                        number_of_images= gr.Number(label='Number of images extracted', interactive=False)
                                with gr.Row():
                                    with gr.Column(scale=4):
                                        with gr.Row():
                                            number_of_samples= gr.Number(label='Number of samples', precision=0, value=10)                                    
                                            btn_load_samples= gr.Button(value='Load samples')
                                        with gr.Row():
                                            gallery_extracted= gr.Gallery(label='Samples extracted from scene', object_fit='contain')
                            with gr.Tab("Identification"):                                   
                                with gr.Row():
                                    with gr.Accordion(label="Face selection", open=True):
                                        with gr.Row():
                                            number_deepface_ident_face_conf= gr.Number(value=0.9, maximum=1, step=0.01, label="Discard confidence", info="Discard face below this threshold")
                                            number_ident_hash_tolerance= gr.Number(label='Hash tolerance', info='Higher number for less images', precision=0, value=15)
                                with gr.Row():
                                    btn_group= gr.Button('Extract and group', variant='stop')
                                    btn_ident= gr.Button('Run identification')
                                with gr.Row():
                                    html_ident_result= gr.HTML(label='Result', value='Progress')
                                with gr.Row():
                                    @gr.render(inputs=[state_scene_stash], triggers=[state_scene_stash.change])
                                    def render_faces(state):
                                        logger.info(f"render_faces state: {state}")
                                        if not isinstance(state, dict):
                                            return
                                        ungrouped: List[int]= state.get('ungrouped', [])
                                        groups: Dict[str, List[int]]= state.get('groups', {})
                                        with get_session() as session:
                                            html=f"<p>Ungrouped count: {len(ungrouped)}<p>"
                                            with gr.Column():
                                                for group_name, group_items in groups.items():
                                                    html+=f"<p>{group_name}: {len(group_items)}</p>" 
                                                with gr.Row():
                                                    gr.HTML(value=html)
                                                groups['']= ungrouped
                                                group_list= list(groups.keys())
                                                for group_name, face_list in groups.items():
                                                    with gr.Row():
                                                        if group_name:
                                                            txt_current_group_name= gr.Text(visible=False, value=group_name)
                                                            txt_group_name= gr.Text(label='Group name', value=group_name, info='Use to change the group name or input an existing group name to merge.')
                                                            txt_group_name.blur(change_group_name, inputs=[txt_current_group_name, txt_group_name, state_scene_stash], outputs=state_scene_stash)
                                                            txt_group_name.submit(change_group_name, inputs=[txt_current_group_name, txt_group_name, state_scene_stash], outputs=state_scene_stash)
                                                        else:
                                                            gr.Label(value='Ungrouped')
                                                    with gr.Row():
                                                        for face_id in face_list:
                                                            face: DeepfaceFace= session.get(DeepfaceFace, face_id)
                                                            if face is None:
                                                                continue                                            
                                                            with gr.Group():
                                                                with gr.Row():
                                                                    txt_face_id= gr.Text(visible=False, value=face.id)
                                                                    img_face= gr.Image(value=get_face_image_path(face), height="200px", label=face.id)
                                                                with gr.Row():
                                                                    face_html= gr.HTML(value=f"""
                                                                            <p>[{face.performer.id if face.performer is not None else ''}]
                                                                            {face.performer.name if face.performer is not None else ''}</p>
                                                                            <p>Size {face.w}x{face.h}</p>
                                                                            <p>Confidence : {round(face.confidence, 3)}</p>
                                                                            <p>{face.age} yo
                                                                            {face.race} ({round(face.race_confidence, 3)})
                                                                            {face.gender} ({round(face.gender_confidence,3)})
                                                                            </p>
                                                                            """)
                                                                with gr.Row():
                                                                    dd_face_status= gr.Dropdown(choices=[s.value for s in FaceStatus], value=face.status.value, label='Face status')
                                                                    dd_face_group= gr.Dropdown(choices=group_list, value=face.group, label='Face Group', allow_custom_value=True)
                                                                    dd_face_status.change(update_face, inputs=[txt_face_id, dd_face_status, dd_face_group, state_scene_stash], outputs=[state_scene_stash])
                                                                    dd_face_group.change(update_face, inputs=[txt_face_id, dd_face_status, dd_face_group, state_scene_stash], outputs=[state_scene_stash])
                                                                with gr.Row():
                                                                    btn_confirm= gr.Button(value='Confirm', variant='primary')
                                                                    btn_upscale= gr.Button(value='Upscale', variant='huggingface')
                                                                    btn_discard= gr.Button(value='Discard', variant='stop')
                                                                    def handle_confirm():
                                                                        return gr.Dropdown(value=FaceStatus.CONFIRMED.value)
                                                                    def handle_upscale():
                                                                        return gr.Dropdown(value=FaceStatus.UPSCALE.value)
                                                                    def handle_discard():
                                                                        return gr.Dropdown(value=FaceStatus.DISCARD.value)
                                                                    btn_confirm.click(handle_confirm, outputs=dd_face_status)
                                                                    btn_upscale.click(handle_upscale, outputs=dd_face_status)
                                                                    btn_discard.click(handle_discard, outputs=dd_face_status)   
                                                    if state.get('groups_results', {}).get(group_name):
                                                        with gr.Row():
                                                            for result in state.get('groups_results', {}).get(group_name):
                                                                performer= session.get(Performer, result['performer_id'])
                                                                if performer is not None:
                                                                    with gr.Column():
                                                                        with gr.Row():
                                                                            with gr.Column(scale=2):
                                                                                gr.Image(performer.main_image.get_highres_imgfile().get_image_path())
                                                                            with gr.Column(scale=2):
                                                                                txt_perf_id= gr.Text(visible=False, value=performer.id)
                                                                                gr.HTML(value=f"<p>Id: {performer.id}</p><p>{performer.name}</p><p>Score : {result.get('score')}</p>")
                                                                            with gr.Column():
                                                                                btn_assign_confirm= gr.Button(value='Assign and confirm', variant='primary')
                                                                                btn_assign_confirm.click(assign_confirm, inputs=[state_scene_stash, txt_group_name, txt_perf_id], outputs=[state_scene_stash])
                                                                                
                                                                    
                                                with gr.Row():
                                                    gr.Label(value='Discarded')
                                                with gr.Row():
                                                    for face_id in state.get('discarded', []):
                                                        face: DeepfaceFace= session.get(DeepfaceFace, face_id)
                                                        if face is None:
                                                            continue                                            
                                                        with gr.Group():
                                                            with gr.Row():
                                                                txt_face_id= gr.Text(visible=False, value=face.id)
                                                                img_face= gr.Image(value=get_face_image_path(face), height="200px", label=face.id)
                                                            with gr.Row():
                                                                face_html= gr.HTML(value=f"""
                                                                        <p style='color: #F3360D;'>[{face.performer.id if face.performer is not None else ''}]
                                                                        {face.performer.name if face.performer is not None else ''}</p>
                                                                        <p style='color: #F3360D;'>Size {face.w}x{face.h}</p>
                                                                        <p style='color: #F3360D;'>Confidence : {round(face.confidence, 3)}</p>
                                                                        <p style='color: #F3360D;'>{face.age} yo
                                                                        {face.race} ({round(face.race_confidence, 3)})
                                                                        {face.gender} ({round(face.gender_confidence,3)})
                                                                        </p>
                                                                        """)
                                                            with gr.Row():
                                                                dd_face_status= gr.Dropdown(choices=[s.value for s in FaceStatus], value=face.status.value, label='Face status')
                                                                dd_face_group= gr.Dropdown(choices=group_list, value=face.group, label='Face Group', allow_custom_value=True)
                                                                dd_face_status.change(update_face, inputs=[txt_face_id, dd_face_status, dd_face_group, state_scene_stash], outputs=[state_scene_stash])
                                                                dd_face_group.change(update_face, inputs=[txt_face_id, dd_face_status, dd_face_group, state_scene_stash], outputs=[state_scene_stash])
                                                            with gr.Row():
                                                                btn_confirm= gr.Button(value='Confirm', variant='primary')
                                                                btn_upscale= gr.Button(value='Upscale', variant='huggingface')
                                                                btn_discard= gr.Button(value='Discard', variant='stop')
                                                                def handle_confirm():
                                                                    return gr.Dropdown(value=FaceStatus.CONFIRMED.value)
                                                                def handle_upscale():
                                                                    return gr.Dropdown(value=FaceStatus.UPSCALE.value)
                                                                def handle_discard():
                                                                    return gr.Dropdown(value=FaceStatus.DISCARD.value)
                                                                btn_confirm.click(handle_confirm, outputs=dd_face_status)
                                                                btn_upscale.click(handle_upscale, outputs=dd_face_status)
                                                                btn_discard.click(handle_discard, outputs=dd_face_status)                                        
                                                    


        btn_group.click(handler_group_faces,
                        inputs=[state_scene_stash, number_deepface_ident_face_conf, number_ident_hash_tolerance],
                        outputs=[state_scene_stash, html_ident_result]
                        )                                    

        btn_ident.click(ident_faces,
                        inputs=[state_scene_stash, number_deepface_ident_face_conf, number_ident_hash_tolerance],
                        outputs=[state_scene_stash, html_ident_result]
                        )                                    
        btn_extract_images.click(extract_images, 
                                 inputs=[number_hash_tolerance, state_scene_stash],
                                 outputs=[number_of_images, state_scene_stash]
                                 ).then(update_scene_infos, 
                                        inputs=state_scene_stash, 
                                        outputs=[html_scene_infos, gallery_performers, state_scene_stash]
                                        ).then(handle_load_samples,
                                               inputs=[number_of_samples, state_scene_stash],
                                               outputs=[gallery_extracted, state_scene_stash]
                                               )
        btn_load_samples.click(handle_load_samples,
                               inputs=[number_of_samples, state_scene_stash],
                               outputs=[gallery_extracted, state_scene_stash]
                               )
        btn_load_scene_id.click(handler_load_scene, 
                                inputs=[txt_scene_id, state_scene_stash], 
                                outputs=[state_scene_stash]
                                ).then(update_scene_infos, inputs=state_scene_stash, outputs=[html_scene_infos, gallery_performers, state_scene_stash, number_of_images])
        
        txt_scene_id.submit(handler_load_scene, 
                            inputs=[txt_scene_id, state_scene_stash], 
                            outputs=[state_scene_stash]
                            ).then(update_scene_infos, inputs=state_scene_stash, outputs=[html_scene_infos, gallery_performers, state_scene_stash, number_of_images])
        # number_extract_images_per_seconds.change(calculate_nb_images_to_extract, 
        #                                          inputs=[number_frames_per_second, number_duration, number_extract_images_per_seconds], 
        #                                          outputs=[number_images_to_extract]
        #                                          )
        # number_total_frames.change(calculate_nb_images_to_extract, 
        #                            inputs=[number_frames_per_second, number_duration, number_extract_images_per_seconds], 
        #                            outputs=[number_images_to_extract]
        #                            )
