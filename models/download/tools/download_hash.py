import os
import re
import hashlib
import zipfile
import json
from pathlib import Path
from abc import ABC,abstractmethod
from models.conversion.tools.conversion_tools import convert_win_path, convert_unix_path

class HashStrategy(ABC):
    _compress_extensions = {'.zip', '.rar', '.tar.gz', '.7z', '.gz', '.bz2', '.tar'}    
    
    @abstractmethod
    def get_hash(self, path: str) -> str:
        pass

    def _is_compressed_file(self, path: str) -> bool:        
        return os.path.splitext(path)[1].lower() in self._compress_extensions

class FileHashStrategy(HashStrategy):    

    def get_hash(self, path: str) -> str:
        with open(path, 'rb') as f:
            hasher = hashlib.sha256(f.read()).hexdigest()
        return hasher

class DirHashStrategy(HashStrategy):    
    
    def __init__(self, file_hasher: HashStrategy):
        self.file_hasher = file_hasher

    def get_hash(self, path: str) -> str:
        dir_path = Path(path)
        hashes_dict = {}
        
        files = [str(f) for f in dir_path.rglob('*') if f.is_file() and not self._is_compressed_file(path=f)]
        
        for f in sorted(files):
            hashes_dict[f] = self.file_hasher.get_hash(f)
        
        dict_str = json.dumps(hashes_dict, sort_keys=True)
        return hashlib.sha256(dict_str.encode()).hexdigest()

class CompressedHashStrategy(HashStrategy):    

    def get_hash(self, path: str) -> str:
        hashes_dict = {}
        files = []        
        dict_str = json.dumps(hashes_dict, sort_keys=True)
        with zipfile.ZipFile(path, 'r') as z:
            for file in sorted(z.namelist()):
                if not file.endswith('/'):
                    with z.open(file) as f:
                        hasher = hashlib.sha256(f.read()).hexdigest()
                        hashes_dict[file] = hasher
                        files.append(file)
        print(files)        
        dict_str = json.dumps(hashes_dict, sort_keys=True)
        return hashlib.sha256(dict_str.encode()).hexdigest()

class Download_Hash:    

    _compress_extensions = {'.zip', '.rar', '.tar.gz', '.7z', '.gz', '.bz2', '.tar'}
    _re_ip_path = r'\d{4}\.\d{4}\.\d{4}\.\d{4}'

    def __init__(self, download_path: str):
        self.download_path = download_path
        
        self.file_hasher = FileHashStrategy()
        self.dir_hasher = DirHashStrategy(self.file_hasher)
        self.compressed_hasher = CompressedHashStrategy()

    def get_download_hash(self) -> str:
        paths_list = self._parse_download_path()
        hashes_list = [self._get_hash_for_path(path) for path in paths_list]
        return ';'.join(hashes_list)

    def _parse_download_path(self) -> list:        
        if re.search(self._re_ip_path, self.download_path):
            return [convert_win_path(f) if '\\' in self.download_path else convert_unix_path(f) for f in self.download_path.split(';')]
        return self.download_path.split(';')

    def _get_hash_for_path(self, path: str) -> str:        
        if self._is_compressed_file(path):
            return self.compressed_hasher.get_hash(path)
        elif os.path.isdir(path):
            return self.dir_hasher.get_hash(path)
        elif os.path.isfile(path):
            return self.file_hasher.get_hash(path)
        return ""

    def _is_compressed_file(self, path: str) -> bool:        
        return os.path.splitext(path)[1].lower() in self._compress_extensions