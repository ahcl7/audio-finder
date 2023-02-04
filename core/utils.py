import os


def get_file_name(path):
    return os.path.basename(path)
    pass


def get_output_path(path):
    dirname, filename = os.path.split(path)
    base, ext = os.path.splitext(filename)
    output_filename = base + "_out" + ext
    return os.path.join(dirname, output_filename)
