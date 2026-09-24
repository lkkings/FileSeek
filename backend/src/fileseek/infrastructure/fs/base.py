from abc import ABC, abstractmethod
# ==================================================
# FileSystem Interface
# ==================================================

class FileSystem(ABC):


    @abstractmethod
    def open(self, path, mode):
        pass


    @abstractmethod
    def exists(self, path):
        pass


    @abstractmethod
    def is_file(self, path):
        pass


    @abstractmethod
    def stat(self, path):
        pass

    @abstractmethod
    def delete(self,path):
        pass

    @abstractmethod
    def compress(self, path, format="zip"):
        ...

    @abstractmethod
    def decompress(self, path):
        ...

