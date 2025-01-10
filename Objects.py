from dataclasses import dataclass
import pathlib

@dataclass
class Performer:
    id: str
    stash_box: str
    safe_name: str
    metadata_file: pathlib.Path
    stash_box_images_dir: pathlib.Path
    download_metadata: bool= False
    metadata= None