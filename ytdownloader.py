import logging

import requests
import youtube_dl

import utils

# Named Exception
class EndThread(Exception):
    pass
    
class Downloader():
    def __init__(self, new_videos, opts=None):
        self.new_videos = new_videos
        
        opts = opts or {}
        self.hook = opts.get("progress_hooks", logging.debug)
        opts["progress_hooks"] = [self.dispatcher]
        opts["logger"] = logging
        opts["format"] = "mp4"
        
        self.yt = youtube_dl.YoutubeDL(opts)
        self.current_id = ""
        self.current_directory = ""
        
        self.on = True
        self.thread_block = utils.thread_block()
        self.download_thread = utils.thread_manager(self.download).start()
    
    def dispatcher(self, status):
        if not self.on:
            raise EndThread
            
        self.hook(self.current_id, status)
        
        self.thread_block.wait()
        
        if not self.on:
            raise EndThread
            
    def add(self, items):
        if isinstance(items, str):
            self.download_thread.put(items)
        else:
            for item in items:
                self.add(item)
                
    def resume(self):
        logging.info("Start")
        self.thread_block.open()
        
    def pause(self):
        logging.info("Stop")
        self.thread_block.close()
        
    def download(self, item):
        self.current_id = item
        try:
            while True:
                self.thread_block.wait()
                if not self.on:
                    raise EndThread
                if next(self.new_videos):
                    continue
                if not self.on:
                    raise EndThread
                if item == "":
                    return
                logging.info(f"Checking: {item}.")
                try:
                    data = self.yt.extract_info(item, process=False)
                    if data["duration"] > 600:
                        self.hook(item, {"status": "skipped", "title": data["title"]})
                        break
                        
                    if not self.on:
                        raise EndThread
                    
                    logging.info(f"Downloading: {item}.")
                    
                    self.current_directory = self.yt.params["outtmpl"].rsplit("/", 1)[0]
                    self.yt.download([item])
                except youtube_dl.utils.DownloadError as e:
                    msg = e.args[0]
                    if msg == "ERROR: giving up after 0 retries":
                        continue
                    else:
                        if "ERROR: Unable to download webpage: <urlopen error [Errno 11001] getaddrinfo failed> (caused by URLError(gaierror(11001, 'getaddrinfo failed')))" in msg:
                            msg = "Connection Error."
                        self.hook(item, {"status": "error", "msg": msg})
                        continue
                    #elif msg == "ERROR: unable to download video data: Remote end closed connection without response":
                    #    pass
                        
                    logging.warning(f"{item} {msg}")
                    with open("Data/log.txt", "a") as fp:
                        fp.write(f"[{item}] {msg}\n")
                break
        except EndThread:
            return True
            
    def end(self):
        logging.info("End")
        self.on = False
        self.add("")
        self.thread_block.open()
        self.download_thread.join()