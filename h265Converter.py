import subprocess
import sys

from hashlib import md5
from pathlib import Path
from time import localtime


class H265Converter:

    overwrite_flag = ''
    error_output = None
    dry_run = False
    tmp_dir = None
    preserve_source = False
    suffix = None

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

    def eprint(self, *args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    def error_stop(self, *args, **kwargs):
        self.eprint(*args, **kwargs)
        sys.exit(1)

    def destination_dir(self, video, dest_path):
        if dest_path is None:
            return video.parent
        if dest_path.is_dir():
            return dest_path
        print(dest_path.parent.as_posix())
        if dest_path.parent.as_posix() == '.':
            return video.parent
        return dest_path

    def intermediate_name(self):
        if self.tmp_dir:
            prefix = md5(str(localtime()).encode('utf-8')).hexdigest()
            tmp_name = f".{prefix}{self.suffix}"
            return tmp_name
        return None

    def final_path(self, video, dest_path):
        return self.destination_dir(video, dest_path).joinpath(self.new_video_name(video))

    def converted_file(self, video, dest_path):
        if self.tmp_dir:
            converted_directory = self.tmp_dir
            converted_file_name = self.intermediate_name()
            return converted_directory.joinpath(converted_file_name)
        else:
            return self.final_path(video, dest_path)

    def new_video_name(self, video):
        """
        :param video: a Path object to the existing video file
        :return: Returns a path object with the proposed name of the file after conversion.
        """
        return video.with_suffix(self.suffix)

    def convert_video(self, src, dest=None):
        """
        Encodes video to h265.
        :param src: Path to source file
        :param dest: If given, path to destination file; otherwise, this is computed and done in place
        :return: None
        """
        path = Path(src)
        dest_path = None
        if dest is not None:
            dest_path = Path(dest)

        suffixes = ''
        for suffix in path.suffixes:
            suffixes = suffixes + suffix
        if suffixes == self.suffix:
            self.error_output('Skipping ' + src + '; already converted')
            return

        if not path.exists():
            self.error_output('Source ' + src + ' does not exist.')
            return

        new_path = self.converted_file(path, dest_path)
        final_path = self.final_path(path, dest_path)
        if self.tmp_dir:
            print('Temp destination: ' + new_path.as_posix())
        print('Destination: ' + final_path.as_posix())
        if self.overwrite_flag == '-n' and final_path.exists():
            self.error_output(final_path.as_posix() + ' exists')
            return

        if not self.tmp_dir and not final_path.parent.exists():
            print("Creating " + final_path.parent.os_posix())
            if not self.dry_run:
                final_path.parent.mkdir(parents=True, exist_ok=True)

        command = ['ffmpeg', self.overwrite_flag, '-i', path, '-c:v', 'libx265', new_path]
        print(command)

        if not self.dry_run:
            output = subprocess.run(command)
            if output.returncode == 0:
                if self.tmp_dir:
                    final_path.parent.mkdir(parents=True, exists_ok=True)
                    print("Moving " + new_path.as_posix() + " to " + final_path.as_posix() + ".")
                    new_path.rename(final_path)
                if not self.preserve_source:
                    path.unlink()
            else:
                self.error_output('Problem converting ' + src + ' to ' + new_path.as_posix())
                if not self.tmp_dir:
                    final_path.unlink(missing_ok=True)
                return

    def convert_videos(self, files, dest=None):
        for file in files:
            print('Converting ' + file + "...")

            self.convert_video(file, dest)

        print('Done.')
