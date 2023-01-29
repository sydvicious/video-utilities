import os
import shutil
import subprocess
import sys

from hashlib import md5
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

    def __init__(self, suffix='.h265.mp4', overwrite=False, force=False, dry_run=False, tmp_dir=None,
                 preserve_source=False):
        self.suffix = suffix
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

    def tmp_name(self, video):
        if self.tmp_dir:
            time_str = strftime('%Y%m%d%H%M%S', localtime())
            base_name = video.stem.replace(" ", "")
            tmp_name = f".{base_name}{time_str}{self.suffix}"
            return tmp_name
        return video.name

    def new_video_name(self, video):
        """
        :param video: a Path object to the existing video file
        :return: Returns a path object with the proposed name of the file after conversion.
        """
        return Path(video.name).with_suffix(self.suffix)

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
            return

        src_path = src_file.parent
        print(f'Source = {src_file}')

        if dest is None:
            dest_path = src_path
        else:
            dest_path = Path(dest)

        if self.tmp_dir is None:
            tmp_path = dest_path
        else:
            tmp_path = self.tmp_dir

        tmp_file_name = self.tmp_name(src_file)
        tmp_file = tmp_path.joinpath(tmp_file_name)
        print(f'Temp = {tmp_file}')

        dest_file_name = self.new_video_name(src_file)
        dest_file = dest_path.joinpath(dest_file_name)
        print(f'Dest = {dest_file}')

        if self.overwrite_flag == '-n' and dest_file.exists():
            self.error_output(f'{dest_file} exists.')
            return

        log_file = tmp_path.joinpath(self.log_name)
        my_env = os.environ.copy()
        my_env["FFREPORT"] = f'file={log_file}:level=32'

        command = ['ffmpeg', self.overwrite_flag, '-report', '-i', src_file, '-c:v', 'libx265', tmp_file]

        if not self.dry_run:
            tmp_path.mkdir(parents=True, exist_ok=True)

            print(f'Converting {src_file} to {tmp_file}...')
            output = subprocess.run(command, stderr=subprocess.DEVNULL, env=my_env)
            if output.returncode == 0:
                dest_path.mkdir(parents=True, exist_ok=True)
                if self.tmp_dir:
                    print(f"Moving {tmp_file} to {dest_file}.")
                    shutil.move(tmp_file.as_posix(), dest_file.as_posix())
                if not self.preserve_source:
                    src_file.unlink()
            else:
                self.error_output(f'Problem converting {src_file} to {tmp_file}')
                if self.tmp_dir is not None:
                    tmp_file.unlink(missing_ok=True)
                    backup_logfile = tmp_file.parent.joinpath(src_file.name).with_suffix('.err')
                    shutil.copyfile(log_file.as_posix(), backup_logfile)
                return

    def convert_videos(self, files, dest=None):
        for file in files:
            print(f'Converting {file}...')

            self.convert_video(file, dest)

        print('Done.')
