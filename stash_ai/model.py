from utils.custom_logging import get_logger
logger= get_logger("stash_ai.model")
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint, Table, Column, ForeignKey, Integer
from stashapi.stashbox import StashBoxInterface
from typing import Optional, ClassVar, List
from PIL import Image
from datetime import datetime
from stash_ai.config import config
import pathlib
import math
class BaseModel(DeclarativeBase):
    pass

class Performer(BaseModel):
    __tablename__= "performer"
    id: Mapped[int]= mapped_column(primary_key=True)
    name: Mapped[str]
    stash_image: Mapped[Optional[str]]= None
    stash_boxes_id: Mapped[List["PerformerStashBox"]] = relationship(back_populates="performer")
    stashbox_images: Mapped[List["PerformerStashBoxImage"]]= relationship(back_populates="performer")
    stash_updated_at: Mapped[Optional[datetime]]
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
