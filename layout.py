from itertools import cycle
from string import ascii_letters, digits
from tkinter import Tk, ttk, Frame, Button, Scale, filedialog, StringVar, TclError, BooleanVar, Menu

import utils

def scroll(sbar, first, last):
    """ Hide and show scrollbar as needed. """
    
    first, last = float(first), float(last)
    if first <= 0 and last >= 1:
        sbar.grid_remove()
    else:
        sbar.grid()
    sbar.set(first, last)
    
def tk_safe(string):
    return string.encode().decode("CP437")
    
def Tree(parent, gridx, gridy, cs, ws, **frame_args):
    """
    
    parent: parent frame
    gridx: x position in parent frame
    gridy: y position in parent frame
    cs: list of column names
    ws: list of column widths
    **frame_args: extra arguments for container frame

    """
    
    parent.columnconfigure(gridx, weight=1)
    parent.rowconfigure(gridy, weight=1)

    tree_frame = Frame(parent)
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)
    tree_frame.grid(sticky="nwse", column=gridx, row=gridy, **frame_args)

    x = lambda f, l: scroll(xs, f, l)
    y = lambda f, l: scroll(ys, f, l)
    tv = ttk.Treeview(tree_frame, xscroll=x, yscroll=y)
    tv.grid(sticky="nwes")

    xs = ttk.Scrollbar(tree_frame, orient='horizontal', command=tv.xview)
    xs.grid(column=0, row=1, sticky="ew")

    ys = ttk.Scrollbar(tree_frame, orient='vertical', command=tv.yview)
    ys.grid(column=1, row=0, sticky="ns")

    style = ttk.Style()
    style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
    style.configure("Treeview", font=('Consolas', 10))

    tv.heading("#0", text=cs[0], anchor='w')
    tv.column("#0", stretch=0, anchor="w", minwidth=ws[0], width=ws[0])

    tv["columns"] = cs[1:]
    for i, w in zip(cs[1:-1], ws[1:-1]):
        tv.heading(i, text=i, anchor='w')
        tv.column(i, stretch=0, anchor='w', minwidth=w, width=w)

    if len(tv["columns"]) > 0:
        tv.heading(cs[-1], text=cs[-1], anchor='w')
        tv.column(cs[-1], stretch=1, anchor='w', minwidth=ws[-1], width=ws[-1])
    
    def parse_values(values, n):
        if isinstance(values, str):
            values = (values,)
        
        if len(values) > n:
            return len(values[n])
            
        return 0
        
    def double(args):
        if tv.identify("region", args.x, args.y) in ("heading", "separator"):
            column = tv.identify("column", args.x, args.y)
            if column == "#0":
                widths = [tv.column("#0")["minwidth"], *(len(tv.item(i, "text"))*7+24 for i in tv.get_children())]
            else:
                widths = [tv.column(column)["minwidth"], *(parse_values(tv.item(i, "values"), int(column[1:])-1)*7+7 for i in tv.get_children())]
                
            tv.column(column, width=max(widths))
            
    tv.bind("<Double-Button-1>", double)

    return tv

class Variable(StringVar):
    def __init__(self, settings, name):
        super().__init__()
        
        self.set(getattr(settings, name))
        self.trace("w", lambda *args: setattr(settings, name, self.get()))

class Layout(Tk):
    pad = {"padx": 5, "pady": 5}
    
    def __init__(self):
        super().__init__()
        
        self.settings = utils.Settings()
        
        self.attributes("-topmost", True)
        self.title("Youtube")
        self.geometry(self.settings.geometry)
        self.minsize(self.settings.width, self.settings.height)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        self.download_var = Variable(self.settings, "download_file")
        self.keep_var = Variable(self.settings, "keep_file")
        self.key_var = Variable(self.settings, "key")
        self.current_frame = False
        self.btn_vars = {
            "Up": (BooleanVar(), self.play),
            "Left": (BooleanVar(), self.stop),
            "Down": (BooleanVar(), self.delete),
            "Right": (BooleanVar(), self.forward)
        }
        
        self.bind("<KeyRelease>", self.key_up)
        self.bind("<Key>", self.key_down)
        
        self.notebook = self._notebook()
        
        self.protocol("WM_DELETE_WINDOW", self.end)
        
    def _notebook(self):
        notebook = ttk.Notebook(self)
        
        player_frame = self._player_frame()
        settings_frame = self._settings_frame()
        tabs = cycle((False, True))
        
        def frame_change(arg):
            self.current_frame = next(tabs)
        
        notebook.bind("<<NotebookTabChanged>>", frame_change)
        notebook.bind("<Key>", lambda e: "break")
        notebook.add(player_frame, text="Player")
        notebook.add(settings_frame, text="Settings")
        notebook.grid(sticky="nwes")
        
        return notebook
        
    def _player_frame(self):
        frame = Frame(self)
        
        self.tv = Tree(frame, 0, 0, ("Filename",), (365,), **self.pad)
        self.tv["selectmode"] = "browse"
        self.tv.tag_configure("play", background="aquamarine")
        
        def change_width(args):
            """Function to resize the Scale when window is resized."""

            self.scale["length"] = self.winfo_width() - 16
        
        self.scale = Scale(frame, orient="horizontal")
        self.scale.grid(column=0, row=1, **self.pad)
        self.scale.bind("<Configure>", change_width)
        self.scale.bind("<Button-1>", self.pressed)
        self.scale.bind("<ButtonRelease-1>", self.unpressed)
        
        self.log_var = StringVar()
        
        lbl = ttk.Label(frame, textvariable=self.log_var)
        lbl.grid(column=0, row=2, sticky="nw", **self.pad)
        
        self._buttons(frame).grid(column=0, row=3, sticky="nw")
        
        return frame
        
    def insert(self, text, filepath):
        try:
            self.tv.insert("", "end", text=text, values=(text, filepath))
        except TclError:
            self.tv.insert("", "end", text=tk_safe(text), values=(text, filepath))
        
    def _buttons(self, parent):
        btn_frame = ttk.Frame(parent)

        self.play_btn = ttk.Button(btn_frame, text="⬆ Play", command=self.play)
        self.play_btn.grid(column=1, **self.pad)
                             
        stop_btn = ttk.Button(btn_frame, text="⬅ Stop", command=self.stop)
        stop_btn.grid(column=0, row=1, **self.pad)

        delete_btn = ttk.Button(btn_frame, text="⬇ Delete", command=self.delete)
        delete_btn.grid(column=1, row=1, **self.pad)

        forward_btn = ttk.Button(btn_frame, text="➡ Keep", command=self.forward)
        forward_btn.grid(column=2, row=1, **self.pad)

        self.new_btn = Button(btn_frame, text="Download new", command=self.check_new)
        self.new_btn.grid(column=3, row=1, **self.pad)

        return btn_frame
        
    def pressed(self, args):
        print("pressed")
        
    def unpressed(self, args):
        print("unpressed")
        
    def _settings_frame(self):
        frame = Frame(self)
        frame.columnconfigure(0, weight=1)
        
        subframe = Frame(frame)
        subframe.columnconfigure(1, weight=1)
        subframe.grid(columnspan=3, sticky="we")
        
        ttk.Label(subframe, text="Download File:").grid(sticky="e", padx=5, pady=(20, 5))
        entry = ttk.Entry(subframe, textvariable=self.download_var, state="readonly")
        entry.grid(column=1, row=0, sticky="we", padx=5, pady=(20, 5))
        cmd = lambda: self.browse(self.download_var)
        btn = ttk.Button(subframe, text="Browse Files", command=cmd)
        btn.grid(column=2, row=0, padx=5, pady=(20, 5))
        
        lbl = ttk.Label(subframe, text="Keep File:")
        lbl.grid(column=0, row=1, sticky="e", **self.pad)
        entry = ttk.Entry(subframe, textvariable=self.keep_var, state="readonly")
        entry.grid(column=1, row=1, sticky="we", **self.pad)
        cmd = lambda: self.browse(self.keep_var)
        btn = ttk.Button(subframe, text="Browse Files", command=cmd)
        btn.grid(column=2, row=1, **self.pad)
        
        self.settings_log_var = StringVar()
        self.channel_var = StringVar()
        
        def validate_key():
            try:
                key = self.clipboard_get()
            except TclError:
                self.settings_log_var.set("Invalid Key.")
            else:
                if len(key)==39 and set(key) <= set(digits+ascii_letters+"-_"):
                    self.key_var.set(key)
                else:
                    self.settings_log_var.set("Invalid Key.")
                    
        ttk.Label(subframe, text="Key").grid(column=0, row=2, sticky="e", **self.pad)
        entry = ttk.Entry(subframe, textvariable=self.key_var, state="disabled", show="*")
        entry.grid(column=1, row=2, sticky="we", **self.pad)
        btn = ttk.Button(subframe, text="Paste Key", command=validate_key)
        btn.grid(column=2, row=2, **self.pad)
        
        lbl = ttk.Label(subframe, text="Add Channels:")
        lbl.grid(column=0, row=3, sticky="e", **self.pad)
        entry = ttk.Entry(subframe, textvariable=self.channel_var)
        entry.grid(column=1, row=3, sticky="we", **self.pad)
        entry.bind("<Return>", self.add_channel)
        btn = ttk.Button(subframe, text="Add", command=self.add_channel)
        btn.grid(column=2, row=3)
        
        self.channel_tv = ctv = Tree(frame, 0, 1, ("Channel", "Playlist Code"), (100, 200), **self.pad)
        
        def copy():
            playlist_id = ctv.item(ctv.selection()[0], 'values')[0]
            url = f"https://www.youtube.com/playlist?list={playlist_id}"
            self.clipboard_clear()
            self.clipboard_append(url)
        
        menu = Menu(self, tearoff=0)
        menu.add_command(label="Copy Playlist", command=copy)
        
        def popup(args):
            item = ctv.identify_row(args.y)
            if item:
                ctv.selection_set(item)
                menu.post(args.x_root, args.y_root)
        
        ctv.bind("<Button-3>", popup)
        
        def delete_channel():
            for item_id in ctv.selection():
                item = ctv.item(item_id)
                del self.settings.channels[item["text"]]
                ctv.delete(item["text"])
                
        for name, values in self.settings.channels.items():
            ctv.insert("", "end", name, text=name, values=(values["playlist"], values["searched"]))
            
        btn = ttk.Button(frame, text="Delete", command=delete_channel)
        btn.grid(column=2, row=1, sticky="n", **self.pad)
 
        btn = ttk.Button(frame, text="Save", command=self.save)
        btn.grid(column=0, columnspan=3, row=2, sticky="we", **self.pad)
        
        lbl = ttk.Label(frame, textvariable=self.settings_log_var)
        lbl.grid(column=0, columnspan=3, row=3, sticky="we", **self.pad)
        
        return frame
        
    def save(self):
        self.settings_log_var.set("Saving...")
        self.settings.x = self.winfo_x()
        self.settings.y = self.winfo_y()
        self.settings.width = self.winfo_width()
        self.settings.height = self.winfo_height()
        self.settings.save()
        self.settings_log_var.set("Saved.")
        
    def add_channel(self, *arg):
        print("add_channel")
        
    def channel_insert(self, name, playlist):
        try:
            self.channel_tv.insert("", "end", name, text=name, values=(playlist,))
        except TclError as e:
            self.settings_log_var.set(f"{name} already exists.")
        else:
            self.settings_log_var.set(f"{name} found.")
        self.channel_var.set("")
                    
    def browse(self, var):
        file = filedialog.askdirectory(initialdir=".", title="Browse Files")
        if file:
            var.set(file)
        
    def key_up(self, args):
        if args.keysym in self.btn_vars:
            self.btn_vars[args.keysym][0].set(False)
            
    def key_down(self, args):
        if self.current_frame:
            return
            
        if args.keysym in self.btn_vars and not self.btn_vars[args.keysym][0].get():
            self.btn_vars[args.keysym][0].set(True)
            self.btn_vars[args.keysym][1]()
            
    def play(self):
        print("play")
        
    def stop(self):
        print("stop")
        
    def delete(self):
        print("delete")
        
    def forward(self):
        print("forward")
        
    def check_new(self):
        print("check_new")
        
    def end(self):
        self.save()
        self.destroy()
        
if __name__ == "__main__":
    # Test layout and settings functionality
    main = Layout()
    main.mainloop()