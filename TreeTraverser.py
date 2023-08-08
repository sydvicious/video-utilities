"""

Copyright © 2023 Syd Polk

"""

import datetime
import os
import queue
import re
import sys
import time

from pathlib import Path

import h265Converter

midnight_lower = datetime.datetime.strptime("00:00:00", '%H:%M:%S').time()
midnight_upper = datetime.datetime.strptime("23:59:59", '%H:%M:%S').time()


class TreeTraverser:

    video_suffixes = ['.mp4', '.mkv', '.webm', '.avi', '.ts', '.m4v',
                    '.MP4', '.mpg', '.mov']
    directories_to_skip = ['tmp', '.grab', 'Photos Library.photoslibrary']
    file_pattern_to_skip = '.*\\(copy.*\\)'
    file_pattern_to_skip_re = re.compile(file_pattern_to_skip)

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
    stop_when_complete = False
    error_list = set()
    error_list_file = None
    refresh = 0

    def __init__(self, suffix='.h265.mp4', overwrite=False, force=False, dry_run=False, tmp_dir=None,
                 preserve_source=False, start_time=None, stop_time=None, stop_when_complete=False,
                 refresh=0,error_list_file=None):
        self.suffix = suffix
        self.overwrite = overwrite
        self.force = force
        self.dry_run = dry_run
        self.preserve_source = preserve_source
        self.stop_when_complete = stop_when_complete
        if str(type(refresh)) == "<class \'list\'>":
            self.refresh = refresh[0]
        else:
            self.refresh = refresh
        if error_list_file is not None:
            self.error_list_file = Path(error_list_file)
            if self.error_list_file.is_dir():
                self.error_list_file = Path(self.error_list_file.joinpath('errors.list'))
        if tmp_dir:
            self.tmp_dir = Path(tmp_dir)
            self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.converter = h265Converter.H265Converter(suffix, overwrite, force, dry_run, tmp_dir, preserve_source)
        if start_time is not None:
            self.start_time = datetime.datetime.strptime(start_time, '%H:%M:%S').time()
        if stop_time is not None:
            self.stop_time = datetime.datetime.strptime(stop_time, '%H:%M:%S').time()

    def write_error(self, path):
        if path not in self.error_list:
            self.error_list.add(path)
            if self.error_list_file is not None:
                error_file = self.error_list_file.open('a')
                error_file.write(f'{path}\n')
                error_file.close()

    def read_errors(self):
        if self.error_list_file is not None and self.error_list_file.exists():
            error_file = self.error_list_file.open('r')
            files = error_file.readlines()
            error_file.close()
            for file in files:
                self.error_list.add(file.strip())

    def should_convert(self, path):
        path_suffix = path.suffix.lower()
        if not (path_suffix in self.video_suffixes):
            return False
        if self.file_pattern_to_skip_re.match(str(path)):
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

            elif self.stop_time < self.start_time \
                    and (self.start_time < now < midnight_lower
                         or midnight_upper < now < self.stop_time):
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
            if self.file_queue.qsize() == 0:
                print('Queue currently empty.')
            else:
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
        start_time = datetime.datetime.now()
        root = Path(source)
        count = 0
        space = 0
        if dest:
            dest_path = Path(dest)
        else:
            dest_path = root
        rechecking = False
        stop_file = Path("/tmp/stop")
        while True:
            self.read_errors()
            for top, dirs, files in os.walk(root):
                for skip in self.directories_to_skip:
                    if skip in dirs:
                        dirs.remove(skip)
                for file in files:
                    video = os.path.join(top, file)
                    path = Path(video)
                    if video in self.error_list:
                        continue
                    if not self.should_convert(path):
                        continue
                    subdir = Path(top).relative_to(root)
                    final_dest = dest_path.joinpath(subdir)
                    if video not in self.file_set:
                        size = path.stat().st_size
                        mtime = path.stat().st_mtime
                        print(f'{video} ({self.size_string(size)}) -> {final_dest}')
                        self.file_set.add(video)
                        self.file_queue.put((size, video, final_dest, mtime))
                        count += 1
                        space += size

            print("")
            while not self.file_queue.empty():
                if stop_file.exists():
                    print(f'{datetime.datetime.now()}: Stop file {stop_file} exists. Remove it and restart to continue.', file=sys.stderr)
                    exit(1)
                size_tag = self.size_string(space)
                print(f'{datetime.datetime.now()}: {count} files; {size_tag}')
                print("")
                if not self.wait_for_window():
                    break
                size, video, dest, mtime = self.file_queue.get()
                path = Path(video)
                if path.stat().st_size > size:
                    print(f'{video} has changed size since queue. Removing and letting the refresh put it back.')
                    continue
                threshold = mtime + 12 * 60 * 60
                if path.stat().st_mtime > threshold:
                    print(f'{video} is being processed too fast; need to let any recording finish. Removing and letting the refresh put it back.')
                    continue
                if not self.converter.convert_video(video, dest):
                    self.write_error(video)
                    print("")
                self.file_set.remove(video)
                count -= 1
                space -= size
                print("")
                if self.refresh > 0:
                    current_time = datetime.datetime.now()
                    duration = current_time - start_time
                    if duration.seconds > self.refresh:
                        print('Rechecking files...')
                        start_time = datetime.datetime.now()
                        rechecking = True
                        break

            if self.stop_when_complete:
                break
            if not rechecking:
                time.sleep(600)
                rechecking = False
        print(f"{datetime.datetime.now()}: Done.")





