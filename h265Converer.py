
import subprocess
import sys

from pathlib import Path


class H265Converter:

    overwrite_flag = ''
    error_output = None
    dry_run = False
    files = []
    dest = None
    dest_is_directory = True
    dest_path = None

    def __init__(self, files, overwrite=False, force=False, dry_run=False, dest=None):
        if overwrite:
            self.overwrite_flag = '-y'
        else:
            self.overwrite_flag = '-n'
        if force:
            self.error_output = self.eprint
        else:
            self.error_output = self.error_stop
        self.dry_run = dry_run
        self.files = files
        self.dest = dest
        if dest:
            self.dest_path = Path(dest[0])
            if self.dest_path.exists():
                self.dest_is_directory = self.dest_path.is_dir()
            else:
                last = self.dest[-1]
                self.dest_is_directory = last == '/'

    def eprint(self, *args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)

    def error_stop(self, *args, **kwargs):
        self.eprint(*args, **kwargs)
        sys.exit(1)

    def destination(self, video, suffix='.h265.mp4'):
        if self.dest is None:
            return self.new_video_name(video, suffix)
        if self.dest_is_directory:
            if not self.dest_path.exists():
                print("Creating " + dest_path.os_posix())
                if not self.dry_run:
                    self.dest_path.mkdir(parents=True,exist_ok=True)
            return self.new_video_name(self.dest_path.joinpath(video.name()), suffix)
        print(self.dest_path.parent.as_posix())
        if self.dest_path.parent.as_posix() == '.':
            return self.new_video_name(video.parent.joinpath(self.dest_path), suffix)
        return self.new_video_name(self.dest_path.parent.joinpath(video.name), suffix)

    def new_video_name(self, video, suffix='.h265.mp4'):
        """
        :param video: a Path object to the existing video file
        :param suffix: the new suffix of the file.
        :return: Returns a path object with the proposed name of the file after conversion.
        """
        return video.with_suffix(suffix)

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

        new_path = self.destination(path)
        print('Destination: ' + new_path.as_posix())

        command = ['ffmpeg', self.overwrite_flag, '-i', path, '-c:v', 'libx265', '-x265-params', 'lossless=1', new_path]
        print(command)
        if not self.dry_run:
            output = subprocess.run(command)
            if output.returncode != 0:
                self.error_output('Problem converting ' + src + ' to ' + new_path.as_posix())

    def convert_videos(self):
        for file in self.files:
            print('Converting ' + file + "...")

            self.convert_video(file)

        print('Done.')
