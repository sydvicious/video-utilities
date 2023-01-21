import datetime
import os
import queue
import time

from pathlib import Path

import h265Converter

midnight_lower = datetime.datetime.strptime("00:00:00", '%H:%M:%S').time()
midnight_upper = datetime.datetime.strptime("23:59:59", '%H:%M:%S').time()


class TreeTraverser:

    video_suffixes=['.mp4', '.mkv', '.mov', '.webm', '.avi', '.ts', '.srt', '.m3u', '.m4v', '.m4a', '.MOV',
                    '.sub', '.MP4', '.mpg']

    suffix = ''
    overwrite = False
    force = False
    dry_run = False
    tmp_dir = None
    preserve_source = False
    file_queue = queue.PriorityQueue()
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
        if not (path.suffix in self.video_suffixes):
            return False
        suffixes = ''
        for suffix in path.suffixes:
            suffixes = suffixes + suffix
        if suffixes == self.suffix:
            return False
        return True

    def wait_for_window(self):
        if self.start_time is None and self.stop_time is None:
            return

        while True:
            now = datetime.datetime.now().time()
            # Check if current time is later than start_time
            if self.start_time is not None and self.stop_time is None:
                if midnight_upper > now > self.start_time:
                    return

            # Check if current time is earlier than stop_time
            elif self.start_time is None and self.stop_time is not None:
                if midnight_lower < now < self.stop_time:
                    return

            # Check to see if current_time is between start_time and stop_time
            elif self.start_time < self.stop_time and self.start_time < now < self.stop_time:
                return

            elif self.stop_time < self.start_time and self.stop_time < now < self.start_time:
                return

            new_hour = now.hour
            new_minute = now.minute + 10
            if new_minute > 60:
                new_minute -= 60
                new_hour += 1
                if new_hour == 24:
                    new_hour = 0
            new_time = datetime.time(new_hour, new_minute, now.second)
            print("[" + str(now) + "] Waiting; will check again at " + str(new_time))
            time.sleep(600)

    def traverse(self, source, dest=None):
        root = Path(source)
        for top, dirs, files in os.walk(root):
            top_path = Path(top)
            if top_path.name == 'tmp':
                continue
            for file in files:
                video = os.path.join(top, file)
                path = Path(video)
                if not self.should_convert(path):
                    continue
                print(video)
                subdir = Path(file).parent.as_posix()
                final_dest = os.path.join(top, subdir)
                self.file_queue.put((path.stat().st_size, video, final_dest))

        while not self.file_queue.empty():
            self.wait_for_window()
            _, video, dest = self.file_queue.get()
            self.converter.convert_video(video, dest)

        print ("Done.")





