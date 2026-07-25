import os
import hashlib
from typing import List, Optional
from rag.services.base import BaseService

class DatasetVersionService(BaseService):
    """
    Computes SHA-256 composite hash for version tracking and cache invalidation.
    """
    DEFAULT_FILES = [
        os.path.join("structured_db", "foods.json"),
        os.path.join("structured_db", "conditions.json"),
        os.path.join("structured_db", "goals.json"),
        os.path.join("structured_db", "allergies.json"),
        os.path.join("rag", "rag_data.json")
    ]

    def __init__(self, data_dir: Optional[str] = None, file_list: Optional[List[str]] = None):
        if data_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_dir = os.path.join(base_dir, "data")
        self.data_dir = data_dir

        if file_list is None:
            self.file_paths = [os.path.join(self.data_dir, rel_path) for rel_path in self.DEFAULT_FILES]
        else:
            self.file_paths = file_list

    def compute_dataset_hash(self) -> str:
        hasher = hashlib.sha256()
        for file_path in sorted(self.file_paths):
            if os.path.exists(file_path):
                hasher.update(file_path.encode('utf-8'))
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
            else:
                hasher.update(f"MISSING:{file_path}".encode('utf-8'))
        return hasher.hexdigest()
