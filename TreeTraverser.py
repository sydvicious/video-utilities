import datetime
import os
import queue
import time

from pathlib import Path

import h265Converter

midnight_lower = datetime.datetime.strptime("00:00:00", '%H:%M:%S').time()
midnight_upper = datetime.datetime.strptime("23:59:59", '%H:%M:%S').time()


class TreeTraverser:

    video_suffixes = ['.mp4', '.mkv', '.mov', '.webm', '.avi', '.ts', '.m4v', '.MOV',
                    '.MP4', '.mpg']
    directories_to_skip = ['tmp', '.grab']

    suffix = ''
    overwrite = False
    force = False
    dry_run = False
    tmp_dir = None
    preserve_source = False
    file_queue = queue.PriorityQueue()
    file_set = set()
    converter = None
    start_time = None
    stop_time = None

    def __init__(self, suffix='.h265.mp4', overwrite=False, force=False, dry_run=False, tmp_dir=None,
                 preserve_source=False, start_time=None, stop_time=None):
        self.suffix = suffix
        self.overwrite = overwrite
        self.force = force
        self.dry_run = dry_run
        self.preserve_source = preserve_source
        if tmp_dir:
            self.tmp_dir = Path(tmp_dir)
            self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.converter = h265Converter.H265Converter(suffix, overwrite, force, dry_run, tmp_dir, preserve_source)
        if start_time is not None:
            self.start_time = datetime.datetime.strptime(start_time, '%H:%M:%S').time()
        if stop_time is not None:
            self.stop_time = datetime.datetime.strptime(stop_time, '%H:%M:%S').time()

    def should_convert(self, path):
        path_suffix = path.suffix
        if not (path_suffix in self.video_suffixes):
            return False
        suffixes = ""
        for suffix in reversed(path.suffixes):
            suffixes = suffix + suffixes
            if suffixes == self.suffix:
                return False
        return True

    def wait_for_window(self):
        if self.start_time is None and self.stop_time is None:
            return True

        while True:
            now = datetime.datetime.now().time()
            # Check if current time is later than start_time
            if self.start_time is not None and self.stop_time is None:
                if now > self.start_time:
                    return True

            # Check if current time is earlier than stop_time
            elif self.start_time is None and self.stop_time is not None:
                if now < self.stop_time:
                    return True

            # Check to see if current_time is between start_time and stop_time
            elif self.start_time < self.stop_time and self.start_time < now < self.stop_time:
                return True

            elif self.stop_time < self.start_time and self.stop_time < now < self.start_time:
                return True

            new_hour = now.hour
            new_minute = now.minute + 10
            if new_minute >= 60:
                new_minute -= 60
                new_hour += 1
                if new_hour == 24:
                    new_hour = 0
            new_time = datetime.time(new_hour, new_minute, now.second)
            print("[" + str(now) + "] Waiting; will check again at " + str(new_time))
            space, name, _ = self.file_queue.queue[0]
            print(f'Next entry: {name} ({self.size_string(space)})')
            time.sleep(600)
            return False

    def size_string(self, size):
        if size > 1024 * 1024 * 1024 * 1024:
            num = size / (1024 * 1024 * 1024 * 1024)
            unit = 'Tb'
        elif size > 1024 * 1024 * 1024:
            num = size / (1024 * 1024 * 1024)
            unit = 'Gb'
        elif size > 1024 * 1024:
            num = size / (1024 * 1024)
            unit = 'Mb'
        elif size > 1024:
            num = size / 1024
            unit = 'Kb'
        else:
            num = size
            unit = 'bytes'
        return f'{num:.3f} {unit}'

    def traverse(self, source, dest=None):
        root = Path(source)
        count = 0
        space = 0
        while True:
            for top, dirs, files in os.walk(root):
                for skip in self.directories_to_skip:
                    if skip in dirs:
                        dirs.remove(skip)
                for file in files:
                    video = os.path.join(top, file)
                    path = Path(video)
                    if not self.should_convert(path):
                        continue
                    subdir = Path(file).parent.as_posix()
                    final_dest = os.path.join(top, subdir)
                    if video not in self.file_set:
                        size = path.stat().st_size
                        print(f'{video} ({self.size_string(size)}) -> {final_dest}')
                        self.file_set.add(video)
                        self.file_queue.put((size, video, final_dest))
                        count += 1
                        space += size

            size_tag = self.size_string(space)

            print(f'{count} files; {size_tag}')

            while not self.file_queue.empty():
                if not self.wait_for_window():
                    break
                _, video, dest = self.file_queue.get()
                self.file_set.remove(video)
                self.converter.convert_video(video, dest)

        print("Done.")





