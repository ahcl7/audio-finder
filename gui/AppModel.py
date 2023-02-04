from gui.Process import Process
from core.hooks import ee
import json
from core.utils import get_file_name

class AppModel:
    def __init__(self, root):
        self.a_path = ""
        self.f_path = ""
        self.g_path = ""
        self.replace_paths = []
        self.b_paths = []
        self.load_setting_from_file()
        self.update_processes()
        self.root = root;
        self.processing_id = -1

    def start(self):
        self.processing_id = 0
        self.start_process(self.processing_id)

    def start_process(self, idx):
        ee.emit("log", f"Start processing {get_file_name(self.processes[idx].b_path)}")
        self.processes[idx].find_a()
        self.processes[idx].find_f()
        self.processes[idx].export_to_file()
        self.finish_process(idx)

    def finish_process(self, idx):
        ee.emit("log", f"Finish processing {get_file_name(self.processes[idx].b_path)}")
        self.processing_id = idx + 1
        if self.processing_id >= len(self.b_paths):
            return
        else:
            self.start_process(self.processing_id)



    def update_a_path(self, a_path: str):
        self.a_path = a_path
        self.update_processes()

    def update_b_paths(self, b_paths):
        self.b_paths = b_paths
        self.update_processes()

    def update_f_path(self, f_path):
        self.f_path = f_path
        self.update_processes()

    def update_g_path(self, g_path):
        self.g_path = g_path
        self.update_processes()

    def update_replace_paths(self, replace_paths):
        self.replace_paths = replace_paths
        self.update_processes()

    def update_processes(self):
        self.save_setting_to_file()
        self.processes = [Process(b_path, self.a_path, self.f_path, self.g_path, self.replace_paths) for b_path in
                          self.b_paths]

    def save_setting_to_file(self):
        with open("data.json", "w") as f:
            data = {
                "a_path": self.a_path,
                "b_path": self.b_paths,
                "f_path": self.f_path,
                "g_path": self.g_path,
                "replace_paths": self.replace_paths,
            }
            f.write(json.dumps(data))

    def load_setting_from_file(self):
        try:
            with open("data.json", "r") as f:
                data = json.load(f)
                self.a_path = data["a_path"]
                self.b_paths = data["b_path"]
                self.f_path = data["f_path"]
                self.g_path = data["g_path"]
                self.replace_paths = data["replace_paths"]
        except FileNotFoundError:
            print("data.json doesn't exist!")
