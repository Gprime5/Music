import logging
import os
import re
import requests
import subprocess
import time

from layout import Layout
from music_controller import Control
from ytdownloader import Downloader
import utils

def get_file_set(filename):
    try:
        with open(filename) as fp:
            return set(fp.read().split(",")) - {""}
    except FileNotFoundError:
        with open(filename, "w") as fp:
            return set()
            
def create_wav(filename):
    subprocess.run([
        "ffmpeg",
        "-v", "quiet",
        "-i", filename,
        "-y",
        f"{filename.rsplit('.', 1)[0]}.wav"
    ], creationflags=8)

def get_saved(download_file):
    c = {"mp4": "wav", "wav": "mp4"}
    files = {"mp4": set(), "wav": set()}
    
    for path in set(os.listdir(download_file)):
        filename, ext = path.rsplit(".", 1)
        
        try:
            if filename in files[c[ext]]:
                files[c[ext]].remove(filename)
                yield filename
            else:
                files[ext].add(filename)
        except KeyError:
            os.remove(f"{download_file}/{path}")

class main(Layout):
    def __init__(self):
        super().__init__()
        
        self.channel_thread = utils.thread_manager(self.channel_adder).start()
        self.event_thread = utils.thread_manager(self.run).start()
        self.event_thread.put("load")
        
        self.mainloop()
        
    def iter_new(self):
        checked = set()
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        while True:
            unchecked = self.settings.channels.keys() - checked
            if not unchecked:
                if self.yt.download_thread.queue.qsize() == 0:
                    self.stop_download()
                yield
                continue
                
            for channel in list(unchecked):
                try:
                    parameters = {
                        "key": self.settings.key,
                        "part": "contentDetails",
                        "maxResults": "50",
                        "fields": "nextPageToken,items(contentDetails(videoId))"
                    }
                    parameters["playlistId"] = self.settings.channels[channel]["playlist"]
                    
                    while True:
                        while True:
                            try:
                                self.log_var.set(f"Checking new videos: {channel}.")
                                logging.info(f"Checking new videos: {channel}.")
                                response = requests.get(url, parameters, timeout=2)
                            except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
                                self.log_var.set("Connection Error.")
                                logging.error("Connection Error.")
                                self.stop_download()
                                yield True
                            else:
                                break
                            
                        response = response.json()
                        items = {n["contentDetails"]["videoId"] for n in response["items"]}
                    
                        items.difference_update(self.downloaded, self.download_pending)
                        if items:
                            self.download_pending.update(items)
                            self.yt.add(items)
                            logging.info(f"{channel} added {len(items)} new videos.")
                        else:
                            logging.info(f"{channel}, no new videos.")
                        
                        if self.settings.channels[channel]["searched"] and len(items) < 50:
                            break
                            
                        if response.get("nextPageToken"):
                            parameters["pageToken"] = response["nextPageToken"]
                        else:
                            break
                        if not self.download_pending:
                            self.yt.add("")
                        yield
                            
                    self.settings.channels[channel]["searched"] = True
                    self.settings.save()
                    
                    with open("Data/download_pending.txt", "w") as fp:
                        fp.write(",".join(self.download_pending))
                    checked.add(channel)
                except KeyError:
                    pass
                yield
        
    def run(self, item):
        if item == "load":
            self.download_pending = get_file_set("Data/download_pending.txt")
            self.downloaded = get_file_set("Data/downloaded.txt")
            download_file = self.download_var.get()
            
            self.control = Control(self.scale)
            self.yt = Downloader(self.iter_new(), {
                "progress_hooks": self.hook,
                "outtmpl": f"{download_file}/%(uploader)s - %(title)s.%(ext)s"
            })
            
            saved_iterator = get_saved(download_file)
            try:
                first = next(saved_iterator)
            except StopIteration:
                pass
            else:
                self.insert(first, download_file)
                self.control.load(f"{download_file}/{first}.wav")
                
                for saved in saved_iterator:
                    self.insert(saved, download_file)
                
            self.yt.add(self.download_pending)
        elif item == "play":
            file = self.tv.identify_row(24)
            if file:
                self.tv.item(file, tags="play")
                
                if self.control.playing:
                    self.control.pause()
                    self.play_btn["text"] = "⬆ Play"
                else:
                    self.control.play()
                    self.play_btn["text"] = "⬆ Pause"
        elif item is None:
            self.control.end()
            self.yt.end()
            
            with open("Data/download_pending.txt", "w") as fp:
                fp.write(",".join(self.download_pending))
                
            return True
        elif item.endswith((".wav", ".mp4")):
            try:
                os.remove(item)
            except PermissionError:
                time.sleep(.1)
                self.event_thread.put(item)
        else:
            music_on = self.control.playing
            download_file = self.download_var.get()
            file = self.tv.identify_row(24)
            if file:
                filename = self.tv.item(file, "values")
                self.event_thread.put(f"{filename[1]}/{filename[0]}.wav")
                if item == "delete":
                    self.event_thread.put(f"{filename[1]}/{filename[0]}.mp4")
                else:
                    os.rename(
                        f"{filename[1]}/{filename[0]}.mp4",
                        f"{self.keep_var.get()}/{filename[0]}.mp4"
                    )
                self.tv.delete(file)
                
            file = self.tv.identify_row(24)
            if file:
                filename = self.tv.item(file, "values")
                self.control.load(f"{filename[1]}/{filename[0]}.wav")
                if music_on:
                    self.play()
            else:
                self.control.stop()
                    
    def hook(self, current_id, status):
        if status["status"] == "downloading":
            percent = status["_percent_str"]
            filename = status["filename"].rsplit("\\", 1)[1].rsplit(".", 1)[0]
            eta = status["_eta_str"]
            self.log_var.set(f"{percent} {eta} {filename}")
        else:
            if status["status"] == "finished":
                create_wav(status["filename"])
                
                filename = status["filename"].rsplit(".", 1)[0]
                
                self.insert(filename.rsplit("\\", 1)[1], self.yt.current_directory)
                if self.tv.identify_row(24) and not self.tv.identify_row(48):
                    self.control.load(f"{filename}.wav")
            elif status["status"] == "skipped":
                self.log_var.set(f"Skipped, video too long: {current_id} {status['title']}")
            elif status["status"] == "error":
                self.log_var.set(status["msg"])
                self.stop_download()
                return
            
            self.downloaded.add(current_id)
            self.download_pending.discard(current_id)
            
            with open("Data/downloaded.txt", "a") as fp:
                fp.write(f",{current_id}")
                
            if self.yt.download_thread.queue.qsize() == 0:
                self.stop_download()
                
    def stop_download(self):
        self.yt.pause()
        self.new_btn["relief"] = "raised"
                                   
    def check_new(self):
        if self.new_btn["relief"] == "sunken":
            self.stop_download()
        else:
            if not self.download_pending:
                self.yt.add("")
            self.yt.resume()
            self.new_btn["relief"] = "sunken"
                
    def pressed(self, args):
        self.control.pressed(args)
        
    def unpressed(self, args):
        self.control.unpressed(args)
        
    def play(self):
        self.event_thread.put("play")
        
    def stop(self):
        self.control.stop()
        self.play_btn["text"] = "⬆ Play"
        
    def delete(self):
        self.event_thread.put("delete")
        
    def forward(self):
        self.event_thread.put("forward")
        
    def browse(self, var):
        super().browse(var)
        
        self.yt.yt.params["outtmpl"] = f"{self.settings.download_file}/%(uploader)s - %(title)s.%(ext)s"
        
    def add_channel(self, *args):
        self.channel_thread.put(self.channel_var.get())
        
    def channel_adder(self, item):
        if item is None:
            return True
            
        if item == "":
            return
            
        key = self.key_var.get()
        log = self.settings_log_var
            
        if key == "":
            log.set("Missing API Key.")
            return
            
        log.set(f"Searching for {item}.")
        
        url = "https://www.googleapis.com/youtube/v3/channels"
        parameters = {
            "part": "contentDetails,snippet",
            "fields": "items(contentDetails(relatedPlaylists(uploads)),snippet(title))",
            "key": key
        }
        match = re.match("https://www.youtube.com/user/([a-zA-Z0-9]+)", item)
        if match is not None:
            parameters["forUsername"] = match.group(1)
        else:
            match = re.match("https://www.youtube.com/channel/([a-zA-Z0-9]+)", item)
            if match is not None:
                parameters["id"] = match.group(1)
            elif len(item) == 24:
                parameters["id"] = item
            else:
                parameters["forUsername"] = item
                
        try:
            response = requests.get(url, parameters, timeout=2)
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout):
            log.set("Connection Error.")
            return
            
        if not response.ok:
            log.set(f"{item} not found.")
            return
            
        response = response.json()["items"]
        if not response:
            log.set(f"{item} not found.")
            return
            
        name = response[0]["snippet"]["title"]
        playlist = response[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        
        self.settings.channels[name] = {"playlist": playlist, "searched": False}
        self.channel_insert(name, playlist)
        
    def end(self):
        self.event_thread.put(None)
        self.channel_thread.put(None)
        self.event_thread.join()
        self.channel_thread.join()
        
        super().end()
        
class custom_format():
    def __init__(self, f):
        self.f = f
    def format(self, *args, **kwargs):
        formatted = self.f.format(*args, **kwargs)
        if len(formatted) > 106:
            return f"{formatted[:106]} ..."
        return formatted
    def find(self, *args):
        return self.f.find(*args)
        
if __name__ == "__main__":
    logging.basicConfig(
        style="{",
        level=logging.INFO,
        format=custom_format("[{levelname}] {asctime} {module} {message}"),
        datefmt='%H:%M:%S'
    )
    x = main()