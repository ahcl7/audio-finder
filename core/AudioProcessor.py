import librosa
import soundfile as sf
import io
import numpy as np
import time
import math
from core.hooks import ee
from fastdtw import fastdtw
import itertools
from typing import List
from core.Action import Action, RemoveAction, ReplaceAction
from core.utils import get_file_name, get_output_path

RESAMPLE_METHOD = "soxr_vhq"
TARGET_SAMPLERATE = 44100


def remove_blank(y, sr):
    intervals = librosa.effects.split(y, top_db=20)
    # Split the audio file into non-silent segments
    non_silent_segments = [y[start:end] for [start, end] in intervals]
    idx = list(itertools.chain.from_iterable([list(range(start, end)) for [start, end] in intervals]))
    res = list(itertools.chain.from_iterable(non_silent_segments))
    print(f"before{len(y)}, after{len(res)}")
    return np.asarray(res), idx


def mfcc(audio, win_length=256, nfft=512, fs=16000, hop_length=128, numcep=26):
    """Wraps the librosa MFCC routine.  Somewhat present for historical reasons at this point."""
    return np.transpose(
        librosa.feature.mfcc(y=audio, sr=fs, n_fft=nfft, win_length=win_length, hop_length=hop_length, n_mfcc=numcep)
    )


def get_similar_score(mfcc_arr, arr1, sr):
    mfcc_arr1 = mfcc(arr1, fs=sr)
    distance, _ = fastdtw(mfcc_arr, mfcc_arr1, dist=lambda x, y: np.linalg.norm(x - y))
    return distance / len(arr1)


def adjust_found_segment(arr, arr1, sr):
    cur = get_similar_score(arr, arr1, sr)
    ssl = 0
    ssr = 0
    best = cur
    best1 = cur
    iter = 100
    for i in range(iter):
        shift = int((i + 1) * sr / iter)
        if (shift > len(arr1) / 2):
            break
        tmp = get_similar_score(arr, arr1[shift:], sr)
        if tmp < best:
            best = tmp
            ssl = shift
        tmp = get_similar_score(arr, arr1[:-shift], sr)
        if tmp < best1:
            best1 = tmp
            ssr = shift
    return ssl, ssr


def get_score(arr, block, sr, sr1, mfcc_arr):
    mono = librosa.to_mono(block.T)
    arr1 = librosa.resample(np.asarray(mono), orig_sr=sr, target_sr=sr1)
    arr1, idx_map = remove_blank(arr1, sr1)
    cr = np.correlate(arr1, arr, "full")
    last_idx = np.argmax(cr)
    # last_idx = max(last_idx, len(arr) - 1)
    # last_idx = min(last_idx, len(arr1) - 1)
    begin_idx = last_idx - len(arr) + 1
    if (begin_idx < 0 or last_idx >= len(arr1)):
        return None
    # sl, sr = adjust_found_segment(mfcc_arr, arr1[begin_idx:last_idx + 1], sr1)
    # begin_idx += sl
    # last_idx -= sr
    real_start = idx_map[begin_idx]
    real_end = idx_map[last_idx]
    score = get_similar_score(mfcc_arr, arr1[begin_idx:last_idx + 1], sr1)
    return score, real_start, real_end


def get_peak_score(mean, std, x):
    return (-(x - mean) / std)


def get_time(s):
    h = int(s / 60 / 60)
    m = int((s - h * 60 * 60) / 60)
    ss = s - h * 60 * 60 - m * 60
    return f"{h}:{m}:{ss:.2f}"


def print_offsets(blocks, sf):
    for block in blocks:
        score, block_id, start, end = block
        print(get_time(start / sf), end=" ")
        print(get_time(end / sf))


def overlap(a, b):
    l, r = a
    l1, r1 = b
    l2 = max(l, l1)
    r2 = min(r, r1)
    return l2 <= r2


def remove_overlap_segments(blocks):
    res = []

    def get_last():
        return res[-1]

    for block in blocks:
        (score, _, start, end) = block
        if len(res) == 0 or not overlap((get_last()[2], get_last()[3]), (start, end)):
            res.append(block)
        else:
            last = get_last()
            if (last[0] > score):
                res[-1] = block
    return res


def get_possible_offset(all_blocks):
    if (len(all_blocks) == 0):
        return []
    mean = np.mean([block[0] for block in all_blocks])
    std = np.std([block[0] for block in all_blocks])
    return list(filter(lambda x: get_peak_score(mean, std, x[0]) > 3, all_blocks))


def get_samplerate(file):
    return librosa.get_samplerate(file)


def get_total_frams(file):
    samplerate = librosa.get_samplerate(file)
    duration = librosa.get_duration(filename=file)
    return duration * samplerate


def validate_and_adjust_blocks(found_blocks, blocks, sr, sr1, arr, mfcc_arr):
    if (len(found_blocks) == 0):
        return []
    res = []
    cnt = 0
    cur = 0
    for block in blocks:
        cnt += 1
        cur_block = found_blocks[cur]
        score, block_id, start, end = cur_block
        if (block_id == cnt):
            cur += 1
            ee.emit("log", f"validate block {cur}/{len(found_blocks)}")
            mono = librosa.to_mono(block.T)
            arr1 = librosa.resample(np.asarray(mono), orig_sr=sr, target_sr=sr1)
            arr1, idx_map = remove_blank(arr1, sr1)
            cr = np.correlate(arr1, arr, "full")
            last_idx = np.argmax(cr)
            begin_idx = last_idx - len(arr) + 1
            ssl, ssr = adjust_found_segment(mfcc_arr, arr1[begin_idx:last_idx + 1], sr1)
            begin_idx += ssl
            last_idx -= ssr
            real_start = idx_map[begin_idx]
            real_end = idx_map[last_idx]
            score = get_similar_score(mfcc_arr, arr1[begin_idx:last_idx + 1], sr1)
            res.append((score, block_id, real_start, real_end))
        if (cur >= len(found_blocks)):
            break
    return res


def find_offsets(file1, file2, start=0):
    print(file1)
    file1_name = get_file_name(file1)
    file2_name = get_file_name(file2)
    cnt = 0
    data, samplerate = sf.read(file1)
    print(samplerate)
    samplerate1 = get_samplerate(file2)

    resample_rate = int(samplerate1 / 10)
    ori_mono = librosa.to_mono(data.T)
    resampled_data = librosa.resample(np.asarray(ori_mono), orig_sr=samplerate, target_sr=resample_rate)
    resampled_data, idx1 = remove_blank(resampled_data, resample_rate)
    mfcc_resampled_data = mfcc(resampled_data, fs=resample_rate)

    start_frame = 0
    file1_total_frames = int(data.shape[0] / samplerate * samplerate1)

    blocksize = file1_total_frames * 4
    overlap = file1_total_frames * 2
    file2_total_frames = get_total_frams(file2)
    if (start != 0):
        start_frame = int(start * file2_total_frames)
    # start_frame = file1_total_frames * 2 * 219
    # end_frame = file1_total_frames * 2 * 400
    blocks = sf.blocks(file2, blocksize=blocksize, overlap=overlap, start=start_frame)
    all_blocks = []
    for block in blocks:
        cnt += 1
        print(cnt)
        ee.emit("log",
                f"Finding {file1_name} in {file2_name}: {int((cnt - 1) * (blocksize - overlap) / (file2_total_frames - start_frame) * 100)}%")
        tmp = get_score(resampled_data, block, samplerate1, resample_rate, mfcc_resampled_data)
        if (tmp is not None):
            score, start, end = tmp
            all_blocks.append((score, cnt, start, end))

    blocks = sf.blocks(file2, blocksize=blocksize, overlap=overlap, start=start_frame)
    all_blocks = get_possible_offset(all_blocks)
    all_blocks = validate_and_adjust_blocks(all_blocks, blocks, samplerate1, resample_rate, resampled_data,
                                            mfcc_resampled_data)
    for i in range(len(all_blocks)):
        block = all_blocks[i]
        score, block_id, start, end = block
        start = (block_id - 1) * (blocksize - overlap) + start / resample_rate * samplerate1
        end = (block_id - 1) * (blocksize - overlap) + end / resample_rate * samplerate1
        all_blocks[i] = (score, cnt, int(start + start_frame), int(end + start_frame))
    all_offsets = remove_overlap_segments(all_blocks)
    print_offsets(all_offsets, sf=samplerate1)
    for block in all_offsets:
        _, _, start, end = block
        ee.emit("log", f"Found: {get_time(start / samplerate1)} -> {get_time(end / samplerate1)}")
    return all_offsets


def load_small_audio_file(file, target_sr=TARGET_SAMPLERATE):
    data, sr = sf.read(file)
    return librosa.resample(librosa.to_mono(data.T), orig_sr=sr, target_sr=target_sr)


def convert_to_n_channels(audio, n):
    # if n == 1:
    #     return librosa.to_mono(audio)
    pass


def get_channels(file):
    data, _ = sf.read(file, start=0, stop=1)
    print(_)
    return data.shape[1]


def process_segment(y, l, actions: List[Action]):
    print(l)
    r = l + y.shape[0] - 1
    _actions = list(filter(lambda x: overlap((l, r), (x.l, x.r)), actions))
    cur = l
    res = np.empty((0), float)
    for action in _actions:
        if (isinstance(action, ReplaceAction)):
            print(action.replace_data.shape)
            if (action.l >= cur):
                res = np.concatenate((res, y[(cur - l):(action.l - l)]))
                res = np.concatenate((res, action.replace_data))
            pass
        elif isinstance(action, RemoveAction):
            if action.l > cur:
                res = np.concatenate((res, y[cur - l:action.l - l]))
            pass
        cur = action.r + 1
        if (cur > r):
            break
    if cur < r:
        res = np.concatenate((res, y[cur - l:r + 1 - l]))
    return res


def export(file, outputfile, actions: List[Action]):
    samplerate = get_samplerate(file)
    blocksize = samplerate * 60 * 5
    blocks = sf.blocks(file, blocksize=blocksize)
    total_frames = get_total_frams(file)
    cur = 0
    with sf.SoundFile(outputfile, "w", samplerate=samplerate, channels=1) as f:
        idx = 0
        for block in blocks:
            idx += 1
            ee.emit("log",
                    f"Exporting to {get_file_name(outputfile)}: {int((idx - 1) * blocksize / total_frames * 100)}%")
            tmp = process_segment(librosa.to_mono(block.T), cur, actions)
            if (len(tmp) > 0):
                f.write(tmp)
            cur += block.shape[0]

# print(get_output_path("/Users/apple/Documents/fun/freelancer/audio/b.mp3"))
# print(process_segment(np.arange(100), 0, [ReplaceAction(1, 5, [5, 4, 3, 2, 1])]))
# print(process_segment(np.arange(100), 3, [ReplaceAction(1, 5, [5, 4, 3, 2, 1])]))
# print(process_segment(np.arange(100), 0, [RemoveAction(1, 5)]))
# print(process_segment(np.arange(100), 3, [RemoveAction(1, 5)]))
# print(process_segment(np.arange(100), 3, [RemoveAction(1, 1000)]))
# print(process_segment(np.arange(100), 0, [ReplaceAction(1, 5, [5, 4, 3, 2, 1]), RemoveAction(6, 10)]))
# exit()
# samplerate = get_samplerate("b.mp3")
# endframe = get_total_frams("b.mp3")
#
#
# def get_s(n):
#     global samplerate
#     return n * samplerate

#
# export("b.mp3", "out.mp3", [ReplaceAction(get_s(5), get_s(10), load_small_audio_file("g.mp3")),
#                             ReplaceAction(get_s(15), get_s(20), load_small_audio_file("c.mp3")),
#                             ReplaceAction(get_s(30), endframe, load_small_audio_file("g.mp3"))
#                             ])

# print(remove_overlap_segments([(1, 1, 1, 10), (1, 1, 10, 20), (1, 1, 11, 30)]))
# print(find_offsets("a.mp3", "b.mp3", 0))

# a = [(0.07336328243342195, 90, 46541282, 46792152), (0.07323954865772087, 433, 222929576, 223180446), (0.07203946435430597, 629, 324114014, 324364884), (0.07528864978559681, 749, 385735174, 385986044), (0.07465067082606089, 977, 503412738, 503663608), (0.3263977507258065, 1038, 534617626, 534883856)]
# print_offsets(a, 44100)
# 0:17:37, 15.542588186154758
# 0:24:45, 10.256494726508015
# 1:11:22, 10.75571754307759
# 1:24:11, 9.4169604595297
# 1:56:28, 9.615312054926584
# 2:14:25, 10.858021481298303
# 2:20:35, 10.623113789414806
# 2:25:38, 8.787127911062363
# 2:38:27, 9.537547343817565
# 2:51:25, 9.79493368380567
# 3:16:11, 10.118277714288624

# 3:10:3
# 1:3:16

# 0:17:32, 11.029020868024759
# 0:24:45, 8.862641161606975
# 0:36:46, 9.088256264986272
# 1:3:12, 9.818937448385231
# 1:24:11, 8.78227721620441
# 1:31:9, 9.035827359466346
# 1:37:34, 8.95504482305884
# 1:56:28, 9.100850237662794
# 2:51:26, 8.768178106057595
# 3:10:1, 8.998807250829302
# 3:16:11, 9.24146141685462

# 0:17:37, 12.373059746325263
# 0:24:45, 8.862641161606975
# 1:3:12, 9.818937448385231
# 1:11:22, 9.756453301131751
# 1:24:11, 8.78227721620441
# 1:56:28, 9.100850237662794
# 2:14:25, 9.45031434582849
# 2:20:35, 9.526595705875616
# 2:25:38, 9.75096622165076
# 2:38:27, 9.638194377787617
# 2:51:26, 8.768178106057595
# 3:10:1, 8.998807250829302
# 3:16:11, 9.24146141685462

# 0:17:37, 12.373059746325263
# 0:24:45, 8.862641161606975
# 0:36:46, 9.088256264986272
# 1:3:12, 9.818937448385231
# 1:11:22, 9.756453301131751
# 1:24:11, 8.78227721620441
# 1:56:28, 9.100850237662794
# 2:14:25, 9.45031434582849
# 2:20:35, 9.526595705875616
# 2:25:38, 9.75096622165076
# 2:38:27, 9.638194377787617
# 2:51:26, 8.768178106057595
# 3:10:1, 8.998807250829302
# 3:16:11, 9.24146141685462

# 0:17:37, 12.373059746325263
# 0:24:45, 8.862641161606975
# 0:36:46, 9.088256264986272
# 1:3:12, 9.818937448385231
# 1:11:22, 9.756453301131751
# 1:24:11, 8.78227721620441
# 1:31:9, 9.035827359466346
# 1:37:34, 8.95504482305884
# 1:56:33, 9.184552453121132
# 2:2:24, 9.547416137892595
# 2:14:25, 9.45031434582849
# 2:20:35, 9.526595705875616
# 2:25:38, 9.75096622165076
# 2:38:27, 9.638194377787617
# 2:51:26, 8.768178106057595
# 3:10:1, 8.998807250829302
# 3:16:16, 9.303608874645272

# 1:31:11


# Found: 0:17:35.24 -> 0:17:39.93
# Found: 0:24:45.51 -> 0:24:50.43
# Found: 0:36:47.07 -> 0:36:51.12
# Found: 1:3:16.06 -> 1:3:20.48
# Found: 1:11:21.93 -> 1:11:26.53
# Found: 1:24:12.00 -> 1:24:16.81
# Found: 1:31:11.64 -> 1:31:16.06
# Found: 1:37:37.46 -> 1:37:41.71
# Found: 1:56:31.90 -> 1:56:36.69
# Found: 2:2:23.52 -> 2:2:28.17
# Found: 2:14:24.90 -> 2:14:29.55
# Found: 2:20:35.19 -> 2:20:39.97
# Found: 2:25:37.90 -> 2:25:42.59
# Found: 2:38:27.13 -> 2:38:31.81
# Found: 2:51:27.60 -> 2:51:32.53
# Found: 3:10:3.23 -> 3:10:7.92
# Found: 3:16:13.93 -> 3:16:18.68
