from utils.custom_logging import get_logger
logger= get_logger("stash_ai.model")
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint, Table, Column, ForeignKey, ForeignKeyConstraint
from stashapi.stashbox import StashBoxInterface
from typing import Optional, ClassVar, List
from PIL import Image
from datetime import datetime
from stash_ai.config import config
import pathlib
import math
import enum
from dataclasses import dataclass

class ImageType(enum.Enum):
    STASH_BOX_PERFORMER= "stash_box_performer"
    PERFORMER_MAIN= "performer"
    SCENE_FRAME= "scene_frame"
    FACE= "face"
    BODY= "body"

class BaseModel(DeclarativeBase):
    pass

class Performer(BaseModel):
    __tablename__= "performer"
    id: Mapped[int]= mapped_column(primary_key=True)
    name: Mapped[str]
    stash_image: Mapped[Optional[str]]= None
    main_image_phash: Mapped[Optional[str]]= mapped_column(ForeignKey("image.phash", name='fk_image'))
    main_image: Mapped["Img"]= relationship(foreign_keys=[main_image_phash])
    stash_boxes_id: Mapped[List["PerformerStashBox"]] = relationship(back_populates="performer")
    stashbox_images: Mapped[List["PerformerStashBoxImage"]]= relationship(back_populates="performer")
    stash_updated_at: Mapped[Optional[datetime]]
    images: Mapped[List["Img"]]= relationship(secondary="performers_images")    
    def get_stash_image_url(self) -> str|None:
        if self.stash_image is None:
            return None
        return f"{config.stash_base_url}{self.stash_image}" 
       
    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Id: {self.id} Name: {self.name} Image: {self.stash_image}, Stash Boxes : {self.stash_boxes_id})"

class PerformerStashBoxImage(BaseModel):
    __tablename__= "performer_stashbox_images"
    image_id: Mapped[str]= mapped_column(primary_key=True)
    performer_id: Mapped[str]= mapped_column(ForeignKey("performer.id"), primary_key=True)
    stash_box_id: Mapped[str]= mapped_column(ForeignKey("stash_box.id"), primary_key=True)
    url: Mapped[str]
    relative_path: Mapped[str]
    width: Mapped[Optional[int]]
    height: Mapped[Optional[int]]
    content_type: Mapped[Optional[str]]
    phash: Mapped[Optional[str]]
    last_status_code: Mapped[Optional[int]]
    stash_box: Mapped["StashBox"]= relationship(back_populates="performer_images")
    performer: Mapped["Performer"]= relationship(back_populates="stashbox_images")

    _image_path: ClassVar[pathlib.Path]= None
    
    def get_image_path(self):
        if self.relative_path is None:
            return None
        if self._image_path is None:
            self._image_path= config.data_dir.joinpath(self.relative_path)
            
        return self._image_path
    
    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Image id: {self.image_id} Performer Id : {self.performer_id} Performer name: {self.performer.name} Stash box : {self.stash_box.name})"

class PerformerStashBox(BaseModel):
    __tablename__ = "performer_stash_box"
    performer_id: Mapped[str]= mapped_column(ForeignKey("performer.id"), primary_key=True)
    stash_box_id: Mapped[str]= mapped_column(ForeignKey("stash_box.id"), primary_key=True)
    stash_id: Mapped[str]
    
    stash_box: Mapped["StashBox"]= relationship(back_populates="performers")
    performer: Mapped["Performer"]= relationship(back_populates="stash_boxes_id")

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Performer Id : {self.performer_id} Performer name: {self.performer.name} Stash box : {self.stash_box.name if self.stash_box is not None else None}, Stash Id : {self.stash_id})"
    
class StashBox(BaseModel):
    __tablename__= "stash_box"
    id: Mapped[str]= mapped_column(primary_key=True)
    name: Mapped[str]
    endpoint: Mapped[str]
    api_key: Mapped[str]= None
    performers: Mapped[List["PerformerStashBox"]] = relationship(back_populates="stash_box")
    performer_images: Mapped[List["PerformerStashBoxImage"]] = relationship(back_populates="stash_box")
    __table_args__ = (UniqueConstraint("endpoint", name="uq_stash_box_endpoint_01"),)

    _interface: ClassVar[Optional[StashBoxInterface]]= None
    
    def get_stashboxinterface(self) -> StashBoxInterface:
        if self._interface is not None:
            return self._interface
        logger.info(f"Creating stash box interface for {self.name} at {self.endpoint}")
        self._interface= StashBoxInterface({"endpoint": self.endpoint, "api_key": self.api_key})
        return self._interface
    
    def __str__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Id: {self.id} Name: {self.name} Endpoint: {self.endpoint} Api Key : {'***' if self.api_key else ''})"

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Id: {self.id} Name: {self.name} Endpoint: {self.endpoint} Api Key : {self.api_key})"

performers_scene = Table(
    "performers_scenes",
    BaseModel.metadata,
    Column("performer_id", ForeignKey("performer.id"), primary_key=True),
    Column("scene_id", ForeignKey("scene.id"), primary_key=True),
)
  
class Scene(BaseModel):
    __tablename__= "scene"
    id: Mapped[int]= mapped_column(primary_key=True)
    stash_updated_at: Mapped[Optional[datetime]]    
    title: Mapped[Optional[str]]
    details: Mapped[Optional[str]]
    url: Mapped[str]
    local_file_name: Mapped[str]
    video_codec: Mapped[str]
    width: Mapped[int]
    height: Mapped[int]
    scale: Mapped[int]
    fps: Mapped[float]
    duration: Mapped[float]
    downscale: Mapped[Optional[int]]
    downscale_width: Mapped[Optional[int]]
    downscale_height: Mapped[Optional[int]]
    relative_extract_dir: Mapped[Optional[str]]
    relative_downscale_extract_dir: Mapped[Optional[str]]
    relative_extract_face_dir: Mapped[Optional[str]]
    relative_downscale_extract_face_dir: Mapped[Optional[str]] 
    hash_tolerance: Mapped[Optional[int]]
    nb_images: Mapped[Optional[int]]
    extraction_time: Mapped[Optional[float]]
    face_detector: Mapped[Optional[str]]
    extends_face_detection: Mapped[Optional[float]]
    nb_faces: Mapped[Optional[int]]    
    performers: Mapped[List[Performer]]= relationship(secondary=performers_scene)
    images: Mapped[List["Img"]]= relationship(secondary="scenes_images")
    
    def number_of_frames(self) -> int:
        if self.fps is None or self.duration is None:
            return 0
        return math.ceil(self.fps * self.duration)
    def get_extract_dir(self) -> pathlib.Path:
        if self.relative_extract_dir is None:
            return None
        return config.data_dir.joinpath(self.relative_extract_dir)

    def get_downscale_extract_dir(self) -> pathlib.Path:
        if self.relative_downscale_extract_dir is None:
            return None
        return config.data_dir.joinpath(self.relative_downscale_extract_dir)

    def get_extract_face_dir(self) -> pathlib.Path:
        if self.relative_extract_face_dir is None:
            return None
        return config.data_dir.joinpath(self.relative_extract_face_dir)

    def get_dowscale_extract_face_dir(self) -> pathlib.Path:
        if self.relative_downscale_extract_face_dir is None:
            return None
        return config.data_dir.joinpath(self.relative_downscale_extract_face_dir)

    def get_url(self) -> str|None:
        if self.url is None:
            return None
        return f"{config.stash_base_url}{self.url}"

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Id: {self.id} Updated: {self.stash_updated_at} Title: {self.title} Url: {self.url} Codec: {self.video_codec} Size: {self.width}x{self.height} Downscale : {self.downscale} ({self.downscale_width}x{self.downscale_height}) Nb Images: {self.nb_images} Faces: {self.nb_faces} Performers: {self.performers})"

class ImgFile(BaseModel):
    __tablename__= "image_file"
    id: Mapped[int]= mapped_column(primary_key=True, autoincrement=True)
    phash: Mapped[str]= mapped_column(ForeignKey("image.phash"))
    scale: Mapped[int]
    content_type: Mapped[Optional[str]]
    mode: Mapped[str]
    format: Mapped[str]
    relative_path: Mapped[str]
    width: Mapped[int]
    height: Mapped[int]
    img: Mapped["Img"]= relationship(back_populates="files")
    _relative_path: ClassVar[pathlib.Path]= None
    __table_args__ = (UniqueConstraint("phash", "scale", name="uq_image_file_phash_scale"),)
    
    def get_image_path(self):
        if self.relative_path is None:
            return None
        if self._relative_path is None:
            self._relative_path= config.data_dir.joinpath(self.relative_path)
            
        return self._relative_path

    def exists(self):
        return self.relative_path and self.get_image_path().exists()

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (phash : {self.phash} scale: {self.scale} size: {self.width}x{self.height}, format: {self.format} mode: {self.mode}, content-type: {self.content_type}, relative_path: {self.relative_path})"

class ImgUri(BaseModel):
    __tablename__ = "image_uri"
    uri: Mapped[str]= mapped_column(primary_key=True)
    image_pash: Mapped[str]= mapped_column(ForeignKey("image.phash"))
    img: Mapped["Img"]= relationship(back_populates="external_uris")

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (phash : {self.image_pash} Uri : {self.uri})"

performers_images = Table(
    "performers_images",
    BaseModel.metadata,
    Column("performer_id", ForeignKey("performer.id"), primary_key=True),
    Column("image_phash", ForeignKey("image.phash"), primary_key=True),
)

scenes_images = Table(
    "scenes_images",
    BaseModel.metadata,
    Column("scene_id", ForeignKey("scene.id"), primary_key=True),
    Column("image_phash", ForeignKey("image.phash"), primary_key=True),
)    
class Img(BaseModel):
    __tablename__ = "image"
    phash: Mapped[str]= mapped_column(primary_key=True)
    image_type: Mapped[ImageType]
    external_uris: Mapped[List["ImgUri"]] = relationship(back_populates="img")
    performers: Mapped[List[Performer]]= relationship(secondary=performers_images)
    scenes: Mapped[List[Scene]]= relationship(secondary=scenes_images)
    original_scale: Mapped[Optional[int]]
    files: Mapped[List["ImgFile"]]= relationship(back_populates="img") 
    #original: Mapped[Optional["ImgFile"]]= relationship(foreign_keys=[phash, original_scale])

    #__table_args__ = (ForeignKeyConstraint(["phash", "original_scale"], ["image_file.phash", "image_file.scale"], 'fk_original_img_file'), )
    def get_highres_imgfile(self, check_exists: bool= True) -> ImgFile:
        highresfile: ImgFile= None
        logger.debug(f"Img:get_highres_imgfile files {self.files}")
        for file in self.files:
            if highresfile is None or highresfile.scale < file.scale:
                logger.debug(f"{file.relative_path} check_exists {check_exists} file_exists {file.get_image_path() and file.get_image_path().exists()}")
                if not check_exists or (file.get_image_path() and file.get_image_path().exists()):
                    highresfile= file
        return highresfile

    def original_file(self):
        if self.original_scale is None:
            return None
        for file in self.files:
            if file.scale == self.original_scale:
                return file        

    def original_file_exists(self):
        file= self.original_file()
        return file is not None and file.exists()        

    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (phash : {self.phash} Type: {self.image_type.name} URIs : {self.external_uris}, original_scale: {self.original_scale}, {len(self.files)} file(s))"
     
@dataclass
class Point():
    x: int
    y: int
    
    def __iter__(self):
        yield self.x
        yield self.y

class DeepfaceFace(BaseModel):
    __tablename__ = "deepface_face" 
    id: Mapped[int]= mapped_column(primary_key=True, autoincrement=True)
    _image_analysis_id: Mapped[Optional[int]]= mapped_column(ForeignKey("image_analysis.id", name='fk_image_analysis')) 
    image_analysis: Mapped["ImageAnalysis"]= relationship(back_populates="faces")      
    x: Mapped[int]
    y: Mapped[int]
    w: Mapped[int]
    h: Mapped[int]
    age: Mapped[Optional[int]]
    gender: Mapped[Optional[str]]
    gender_confidence: Mapped[Optional[float]]
    race: Mapped[Optional[str]]
    race_confidence: Mapped[Optional[float]]
    confidence: Mapped[Optional[float]]
    overlapping: Mapped[bool]= False
    performer: Mapped["Performer"]= relationship()
    _performer_id: Mapped[Optional[str]]= mapped_column(ForeignKey("performer.id", name="fk_performer"))
    group: Mapped[Optional[str]]
    relative_path: Mapped[Optional[str]]
    
    _file_path: ClassVar[pathlib.Path]
    
    def get_image_path(self):
        if self.relative_path is None:
            return None
        if self._image_path is None:
            self._file_path= config.data_dir.joinpath(self.relative_path)
        return self._file_path
    
    def get_top_left(self):
        return Point(self.x, self.y)
    
    def get_top_right(self):
        return Point(self.x + self.w, self.y)
    
    def get_bottom_left(self):
        return Point(self.x, self.y + self.h)
    
    def get_bottom_right(self):
        return Point(self.x + self.w, self.y + self.h)
    
    def overlap(self, other) -> bool:
        return not (self.get_top_right().x < other.get_bottom_left().x
                    or self.get_bottom_left().x > other.get_top_right().x
                    or self.get_top_right().y < other.get_bottom_left().y
                    or self.get_bottom_left().y > other.get_top_right().y)
    
    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Id: {self.id} Image analysis id : {self._image_analysis_id} Group : {self.group} Performer id: {self._performer_id} X: {self.x} Y: {self.y} W: {self.w} H: {self.h} Age: {self.age} Gender: {self.gender} {self.gender_confidence} Race: {self.race} ({self.race_confidence}))"

class ImageAnalysis(BaseModel):
    __tablename__ = "image_analysis"
    id: Mapped[int]= mapped_column(primary_key=True, autoincrement=True)
    _image_file_id: Mapped[Optional[int]]= mapped_column(ForeignKey("image_file.id", name='fk_image_file'))    
    image_file: Mapped["ImgFile"]= relationship()
    detector: Mapped[str]
    expand_face: Mapped[float]
    faces: Mapped[List["DeepfaceFace"]]= relationship()
        
    def __repr__(self):
        return f"{self.__class__.__module__}.{self.__class__.__name__} (Id: {self.id} ImgFileId: {self._image_file_id} Detector: {self.detector} Expand face: {self.expand_face}%))"
