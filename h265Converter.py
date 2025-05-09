"""

Copyright © 2023 Syd Polk

"""

import datetime
import os
import shutil
import subprocess
import sys

from pathlib import Path
from time import localtime, strftime


class H265Converter:

    overwrite_flag = ''
    error_output = None
    dry_run = False
    tmp_dir = None
    preserve_source = False
    suffix = None
    log_nane = None
    video_suffixes = []

    def __init__(self, suffix='.v2.mp4', overwrite=False, force=False, dry_run=False, tmp_dir=None,
                 preserve_source=False, video_suffixes=[]):
        self.suffix = suffix
        self.video_suffixes = video_suffixes
        if overwrite:
            self.overwrite_flag = '-y'
        else:
            self.overwrite_flag = '-n'
        if force:
            self.error_output = self.eprint
        else:
            self.error_output = self.error_stop
        self.dry_run = dry_run
        if tmp_dir:
            self.tmp_dir = Path(tmp_dir)
            self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.preserve_source = preserve_source
        time_str = strftime('%Y%m%d%H%M%S', localtime())
        self.log_name = f'h265Converter-{time_str}.log'

    def eprint(self, *args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    def error_stop(self, *args, **kwargs):
        self.eprint(*args, **kwargs)
        sys.exit(1)

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

    def tmp_name(self, video):
        if self.tmp_dir:
            time_str = strftime('%Y%m%d%H%M%S', localtime())
            base_name = video.stem.replace(" ", "")
            tmp_name = f".{base_name}{time_str}{self.suffix}"
            return tmp_name
        return video.name

    def new_video_name(self, video, dest_path):
        """
        :param video: a Path object to the existing video file
        :return: Returns a path object with the proposed name of the file after conversion.
        """
        name = video.name
        stem = video.stem
        extension = video.suffix
        while extension in self.video_suffixes and name != stem:
            newname = stem
            newstem = os.path.splitext(newname)[0]
            extension = os.path.splitext(newname)[1]
            if not (extension in self.video_suffixes):
                break
            name = newname
            stem = newstem

        name = Path(name).with_suffix(self.suffix)
        return dest_path.joinpath(name)

    def print_quantity_with_tag(self, quant, singular, plural):
        print(f'{quant}', end="")
        if quant == 1:
            print(f' {singular}', end="")
        else:
            print(f' {plural}', end="")

    def pretty_print_duration(self, duration):
        if round(duration.seconds) == 0:
            print('0 seconds')
            return

        hours = int(duration.seconds / 3600)
        if hours > 0:
            self.print_quantity_with_tag(hours, "hour", "hours")
            duration -= datetime.timedelta(seconds=hours*3600)
            seconds = int(round(duration.seconds))
            if seconds > 0:
                print(', ', end="")

        minutes = int(duration.seconds / 60)
        if minutes > 0:
            self.print_quantity_with_tag(minutes, "minute", "minutes")
            duration -= datetime.timedelta(seconds=minutes*60)

        seconds = int(round(duration.seconds))
        if (hours > 0) or (minutes > 0):
            if seconds > 0:
                print(', ', end="")
                self.print_quantity_with_tag(seconds, "second", "seconds")
        else:
            self.print_quantity_with_tag(seconds, "second", "seconds")

        print('')

    def convert_video(self, src, dest=None):
        """
        Encodes video to h265.
        :param src: Path to source file
        :param dest: If given, path to destination file; otherwise, this is computed and done in place
        :return: None
        """

        # Setup paths
        # src_path - PosixPath to src directory
        # dest_path - PosixPath to destination directory. If not given, same as path
        # tmp_path - Where to write in-progress file. If not given, same as dest_path, which might also be path
        # src_file - PosixPath to src file
        # tmp_file - PosixPath to in-progress encoding
        # dest_file - PosixPath to final file.

        src_file = Path(src)

        if not src_file.exists():
            self.error_output('Source ' + src + ' does not exist.')
            return False

        src_size = src_file.stat().st_size
        print(f'Source = {src_file} - {self.size_string(src_size)}')

        src_path = src_file.parent

        if dest is None:
            dest_path = src_path
            dest_file = dest_path.joinpath(dest)
        else:
            dest_file = Path(dest)
            dest_path = dest_file.parent

        if not dest_path.exists():
            self.error_output('Dest Path ' + str(dest_path) + ' does not exist.')
            return False

        if self.tmp_dir is None:
            tmp_path = dest_path
        else:
            tmp_path = self.tmp_dir

        tmp_file_name = self.tmp_name(src_file)
        tmp_file = tmp_path.joinpath(tmp_file_name)
        print(f'Temp = {tmp_file}')

        print(f'Dest = {dest_file}')

        if self.overwrite_flag == '-n' and dest_file.exists():
            print(f'{datetime.datetime.now()}: {dest_file} exists.')
            if not self.dry_run and not self.preserve_source:
                src_file.unlink()
            return True

        log_file = tmp_path.joinpath(self.log_name)
        my_env = os.environ.copy()
        my_env["FFREPORT"] = f'file={log_file}:level=32'

        command = ['ffmpeg', self.overwrite_flag, '-report', '-i', src_file, '-c:v', 'libx265', '-c:a', 'aac', '-tag:v', 'hvc1', tmp_file]

        if not self.dry_run:
            start = datetime.datetime.now()

            tmp_path.mkdir(parents=True, exist_ok=True)

            print(f'{start}: Converting {src_file} to {tmp_file}...')
            output = subprocess.run(command, stderr=subprocess.DEVNULL, env=my_env)
            end = datetime.datetime.now()
            duration = end - start

            if output.returncode == 0:
                dest_path.mkdir(parents=True, exist_ok=True)
                print(f'{end}: Wrote {self.size_string(tmp_file.stat().st_size)}.')
                if self.tmp_dir:
                    print(f"{datetime.datetime.now()}: Moving {tmp_file} to {dest_file}.")
                    shutil.move(tmp_file.as_posix(), dest_file.as_posix())
                if not self.preserve_source:
                    src_file.unlink()
            else:
                self.error_output(f'{end}: Problem converting {src_file} to {tmp_file}')
                if self.tmp_dir is not None:
                    tmp_file.unlink(missing_ok=True)
                    backup_logfile = tmp_file.parent.joinpath(src_file.name).with_suffix('.err')
                    shutil.copyfile(log_file.as_posix(), backup_logfile)
                return False
            print(f"{datetime.datetime.now()}: Time: ", end="")
            self.pretty_print_duration(duration)

        return True

    def convert_videos(self, files, dest=None):
        for file in files:
            print(f'{datetime.datetime.now()}: Converting {file}...')

            self.convert_video(file, dest)

        print('{datetime.datetime.now()}: Done.')
