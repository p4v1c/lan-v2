# services/base_service.py

class BaseService:
    """Classe de base pour tous les services."""
    
    def __init__(self, name: str):
        self.name = name
    
    def is_active(self) -> bool:
        raise NotImplementedError
    
    def start(self):
        raise NotImplementedError
    
    def stop(self):
        raise NotImplementedError
