import logging
import os
import time
import winsound

import utils

def get_duration(path):
    """ Returns the duration of the wav file. """
    
    return int((os.path.getsize(path) - 78) / 44100 / 4)
    
def create_temp(path, offset):
    """ Creates a temporary file starting at offset seconds. """
    
    with open(path, "rb") as fp:
        data = fp.read()
        
    start = data[:5]
    duration = int.from_bytes(data[5:8], "little")
    new_duration = int(duration - offset*44100/64).to_bytes(3, "little")
    mid = [new_duration, data[8:75], new_duration]
    end = data[78 + offset*44100*4:]
    
    with open("Data/temp.wav", "wb") as fp:
        fp.write(b"".join([start, *mid, end]))
        
class Control():
    def __init__(self, scale):
        self.scale = scale
        self.repeat = True
        self.path = ""
        self.playing = False
        self.press = False
        self.duration = 100
        
        self.event_thread = utils.thread_manager(self.event_handler).start()
        
    def event_handler(self, item):
        if isinstance(item, str):
            logging.info(f"Load: {item}")
            self.path = item
            self.scale["to"] = self.duration = get_duration(item)
        elif isinstance(item, int):
            logging.info(f"Play: {item}")
            self._play(item)
        elif item is None:
            logging.info(f"End")
            return True
            
    def pressed(self, args):
        self.press = True
        if self.scale.identify(args.x, args.y) in ("trough12", "trough2"):
            ratio = self.duration / (self.scale.winfo_width() - 38)
            self.scale.set((args.x - 19) * ratio)
            
    def unpressed(self, args):
        self.press = False
        if self.scale.identify(args.x, args.y):
            self.playing, playing = False, self.playing
            if self.path and playing:
                self.play()
                
    def load(self, path):
        self.stop()
        self.event_thread.put(path)
        
    def play(self, offset=0):
        if not self.playing:
            self.event_thread.put(offset or self.scale.get())
            
    def _play(self, offset):
        if self.path == "":
            return
            
        path = self.path
        if offset:
            create_temp(path, offset)
            path = "Data/temp.wav"
            
        start_time = time.time() - offset
        winsound.PlaySound(path, winsound.SND_ASYNC)
        self.playing = True
        
        while self.playing:
            progress = time.time() - start_time
            if not self.press:
                self.scale.set(progress)
            if progress > self.duration:
                self.stop()
                if self.repeat:
                    time.sleep(.5)
                    self.play()
            time.sleep(.1)
        else:
            winsound.PlaySound(None, winsound.SND_ASYNC)
            
    def pause(self):
        self.playing = False
        
    def stop(self):
        self.pause()
        self.scale.set(0)
        
    def end(self):
        self.pause()
        self.event_thread.put(None)
        if os.path.exists("Data/temp.wav"):
            os.remove("Data/temp.wav")
        self.event_thread.join()