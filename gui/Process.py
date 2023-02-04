from gui.Status import Status
from core.AudioProcessor import find_offsets, export, get_total_frams, load_small_audio_file, get_samplerate
from core.Action import RemoveAction, ReplaceAction
from core.utils import get_output_path

class Process:
    def __init__(self, b_path: str, a_path: str, f_path: str, g_path: str, replace_paths):
        self.b_path = b_path
        self.a_path = a_path
        self.f_path = f_path
        self.g_path = g_path
        self.replace_paths = replace_paths
        self.a_pos = []
        self.f_pos = []
        self.status = Status.NOT_STARTED

    def find_a(self):
        pass

    def find_f(self):
        pass

    def export_to_file(self):
        f_pos = find_offsets(self.f_path, self.b_path, 80 / 100)
        print(f_pos)
        a_pos = find_offsets(self.a_path, self.b_path, 0.06)
        print(a_pos)
        actions = []
        endframe = get_total_frams(self.b_path)
        cur = 0
        b_sameple_rate = get_samplerate(self.b_path)
        for block in a_pos:
            score, block_id, start, end = block
            actions.append(
                ReplaceAction(start, end, load_small_audio_file(self.replace_paths[cur % len(self.replace_paths)], target_sr=b_sameple_rate)))
            cur += 1
        print(actions)
        if len(f_pos) > 0:
            last_pos = f_pos[-1]
            _, _, _, end = last_pos
            actions.append(ReplaceAction(end + 1, endframe, load_small_audio_file(self.g_path, target_sr=b_sameple_rate)))
        print(actions)
        export(self.b_path, get_output_path(self.b_path), actions)
