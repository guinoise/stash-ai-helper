from utils.custom_logging import get_logger
logger= get_logger("stash_ai.model")
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from stashapi.stashbox import StashBoxInterface
from typing import Optional, ClassVar
from PIL import Image

class BaseModel(DeclarativeBase):
    pass

class Performer(BaseModel):
    __tablename__= "performer"
    id: Mapped[int]= mapped_column(primary_key=True)
    name: Mapped[str]
    
class StashBox(BaseModel):
    __tablename__= "stash_box"
    id: Mapped[str]= mapped_column(primary_key=True)
    name: Mapped[str]
    endpoint: ClassVar[str]= None
    api_key: ClassVar[str]= None
    interface: ClassVar[Optional[StashBoxInterface]]= None
    
class PerformerImage(Image.Image):
    performer: Performer= None
    
    def __init__(self, performer: Performer):
        #super().__init__()
        #self._im= img._im
        self.performer= performer
