from tkinter import *
from tkinter import ttk
from typing import Union
import tkinter as tk
from tkinter import scrolledtext
import tkinter.filedialog as fd
from gui.AppModel import AppModel
from core.hooks import ee
import threading

model: Union[AppModel, None] = None
root: Union[Tk, None] = None
select_a_button: Union[ttk.Button, None] = None
select_b_button: Union[ttk.Button, None] = None
select_f_button: Union[ttk.Button, None] = None
select_g_button: Union[ttk.Button, None] = None
select_replace_button: Union[ttk.Button, None] = None
start_button: Union[ttk.Button, None] = None
a_path_label: Union[ttk.Label, None] = None
b_path_label: Union[ttk.Label, None] = None
f_path_label: Union[ttk.Label, None] = None
g_path_label: Union[ttk.Label, None] = None
last_log_label: Union[ttk.Label, None] = None
all_log_label: Union[scrolledtext.ScrolledText, None] = None
replace_path_label: Union[ttk.Label, None] = None

logs = []


def update_logs_view(log):
    global last_log_label, all_log_label, logs
    last_log_label.config(text=log)
    if (len(logs) == 0) or (logs[-1] != log):
        print("update log")
        logs.append(log)
        all_log_label.insert(tk.END, log + "\n")
        all_log_label.see(tk.END)


def add_log(log):
    update_logs_view(log)


ee.on("log", add_log)


def update_everything():
    global model, a_path_label, b_path_label, replace_path_label
    a_path_label.config(text=model.a_path)
    b_path_label.config(text="\n".join(model.b_paths))
    f_path_label.config(text=model.f_path)
    g_path_label.config(text=model.g_path)
    replace_path_label.config(text="\n".join(model.replace_paths))


def update_a_path(a_path):
    global model
    model.update_a_path(a_path)
    update_everything()


def update_b_path(b_path):
    global model
    model.update_b_paths(b_path)
    update_everything()


def update_f_path(f_path):
    print(f_path)
    global model
    model.update_f_path(f_path)
    update_everything()


def update_g_path(g_path):
    global model
    model.update_g_path(g_path)
    update_everything()


def update_replace_path(replace_path):
    global model
    model.update_replace_paths(replace_path)
    update_everything()


def create_file_selector_frame() -> ttk.Frame:
    global select_a_button, select_b_button, select_f_button
    global select_g_button, a_path_label, b_path_label, f_path_label, g_path_label
    global replace_path_label, last_log_label, select_replace_button, start_button
    frame = Frame(root)

    def select_a():
        filename = fd.askopenfilename(parent=root, title="select a file")
        print(filename)
        if filename:
            update_a_path(filename)

    def select_b():
        files = fd.askopenfilenames(parent=root, title="select files")
        if files:
            update_b_path(list(files))

    def select_f():
        filename = fd.askopenfilename(parent=root, title="select a file")
        if filename:
            update_f_path(filename)

    def select_g():
        filename = fd.askopenfilename(parent=root, title="select a file")
        if filename:
            update_g_path(filename)

    def select_replace():
        files = fd.askopenfilenames(parent=root, title="select files")
        if files:
            update_replace_path(list(files))

    def start():
        thread = threading.Thread(target=model.start)
        thread.start()
        pass

    select_a_button = Button(frame, text="Select A", command=select_a)
    select_a_button.grid(row=0, column=0)
    a_path_label = Label(frame, text=model.a_path)
    a_path_label.grid(row=0, column=1)
    select_b_button = Button(frame, text="Select B", command=select_b)
    select_b_button.grid(row=1, column=0)
    b_path_label = Label(frame, text="")
    b_path_label.grid(row=1, column=1)
    select_f_button = Button(frame, text="Select F", command=select_f)
    select_f_button.grid(row=2, column=0)
    f_path_label = Label(frame, text="")
    f_path_label.grid(row=2, column=1)
    select_g_button = Button(frame, text="Select G", command=select_g)
    select_g_button.grid(row=3, column=0)
    g_path_label = Label(frame, text="")
    g_path_label.grid(row=3, column=1)
    select_replace_button = Button(frame, text="Select C,D,E,...", command=select_replace)
    select_replace_button.grid(row=4, column=0)
    replace_path_label = Label(frame, text="")
    replace_path_label.grid(row=4, column=1)
    start_button = Button(frame, text="Start", command=start)
    start_button.grid(row=5, column=0)
    last_log_label = Label(frame, text="")
    last_log_label.grid(row=7, column=0)
    return frame


def create_processes_frame():
    global model
    return None


def create_log_frame():
    global all_log_label
    frame = Frame(root)
    all_log_label = scrolledtext.ScrolledText(frame, height=50, width=50)
    all_log_label.pack()
    all_log_label.insert("1.0", "nguyen ngoc duong")
    return frame


def start_gui():
    global model, root
    root = Tk()
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)
    model = AppModel(root)
    root.geometry("1000x1000")
    file_selector_frame = create_file_selector_frame()
    update_everything()
    file_selector_frame.grid(row=0, column=0, sticky="nesw")
    log_frame = create_log_frame()
    log_frame.grid(row=0, column=1, sticky="nesw")
    root.mainloop()

