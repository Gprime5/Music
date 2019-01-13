from pathlib import Path
from queue import Queue
from threading import Thread, Event
import json

class Settings():
    def __init__(self):
        Path("Data").mkdir(exist_ok=True)
        Path("Download File").mkdir(exist_ok=True)
        Path("Keep File").mkdir(exist_ok=True)
        
        # Default data
        self.channels = {}
        self.download_file = "Download File"
        self.keep_file = "Keep File"
        self.key = ""
        self.x = 1000
        self.y = 270
        self.height = 350
        self.width = 400
        
        try:
            with open("Data/info.json") as fp:
                self.__dict__.update(json.load(fp))
        except FileNotFoundError:
            with open("Data/info.json", "w") as fp:
                json.dump(self.__dict__, fp, indent=4, sort_keys=True)
            
    def save(self):
        with open("Data/info.json", "w") as fp:
            json.dump(self.__dict__, fp, indent=4, sort_keys=True)
            
    @property
    def geometry(self):
        return f"{self.width}x{self.height}+{self.x}+{self.y}"
            
# Streamline Threads and Queues
class thread_manager(Thread):
    def __init__(self, function):
        super().__init__()
        
        self.queue = Queue()
        self.function = function
        
    def run(self):
        while True:
            if self.function(self.queue.get()):
                break
    
    def put(self, item):
        self.queue.put(item)
        
    def start(self):
        super().start()
        return self
        
# Event method names confuse me so I use this instead
class thread_block(Event):
    def close(self):
        super().clear()
        
    def open(self):
        super().set()
    
