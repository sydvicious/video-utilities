import subprocess
import sys
import tempfile

from hashlib import md5
from pathlib import Path
from time import localtime


class H265Converter:

    overwrite_flag = ''
    error_output = None
    dry_run = False
    files = []
    dest = None
    dest_is_directory = True
    dest_path = None
    tmp_dir = None
    preserve_source = False
    suffix = None

    def __init__(self, files, suffix='.h265.mp4', overwrite=False, force=False, dry_run=False, dest=None, tmp_dir=None,
                 preserve_source=False):
        self.files = files
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
        self.dest = dest
        if tmp_dir:
            self.tmp_dir = Path(tmp_dir[0])
            self.tmp_dir.mkdir(parents=True, exist_ok=True)
        if dest is not None:
            self.dest_path = Path(dest[0])
            if self.dest_path.exists():
                self.dest_is_directory = self.dest_path.is_dir()
            else:
                last = self.dest[-1]
                self.dest_is_directory = last == '/'
        self.preserve_source = preserve_source

    def eprint(self, *args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    def error_stop(self, *args, **kwargs):
        self.eprint(*args, **kwargs)
        sys.exit(1)

    def destination_dir(self, video):
        if self.dest is None:
            return video.parent
        if self.dest_is_directory:
            if not self.dest_path.exists():
                print("Creating " + dest_path.os_posix())
                if not self.dry_run:
                    self.dest_path.mkdir(parents=True, exist_ok=True)
            return self.dest_path
        print(self.dest_path.parent.as_posix())
        if self.dest_path.parent.as_posix() == '.':
            return video.parent
        return self.dest_path

    def intermediate_name(self):
        if self.tmp_dir:
            prefix = md5(str(localtime()).encode('utf-8')).hexdigest()
            tmp_name = f".{prefix}{self.suffix}"
            return tmp_name
        return None

    def final_path(self, video):
        return self.destination_dir(video).joinpath(self.new_video_name(video))

    def converted_file(self, video):
        if self.tmp_dir:
            converted_directory = self.tmp_dir
            converted_file_name = self.intermediate_name()
            return converted_directory.joinpath(converted_file_name)
        else:
            return self.final_path(video)

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

        if not path.exists():
            H265Converter.error_output('Source ' + src + ' does not exist.')
            return

        new_path = self.converted_file(path)
        final_path = self.final_path(path)
        if self.tmp_dir:
            print('Temp destination: ' + new_path.as_posix())
        print('Destination: ' + final_path.as_posix())
        if self.overwrite_flag == '-n' and final_path.exists():
            self.error_output(final_path.as_posix() + ' exists')
            return

        command = ['ffmpeg', self.overwrite_flag, '-i', path, '-c:v', 'libx265', new_path]
        print(command)
        if not self.dry_run:
            output = subprocess.run(command)
            if output.returncode == 0:
                if self.tmp_dir:
                    print("Moving " + new_path.as_posix() + " to " + final_path.as_posix() + ".")
                    new_path.rename(final_path)
                if not self.preserve_source:
                    path.unlink()
            else:
                self.error_output('Problem converting ' + src + ' to ' + new_path.as_posix())
                if not self.tmp_dir:
                    final_path.unlink(missing_ok=True)
                return

    def convert_videos(self):
        for file in self.files:
            print('Converting ' + file + "...")

            self.convert_video(file)

        print('Done.')
