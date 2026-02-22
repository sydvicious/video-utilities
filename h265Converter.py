"""

Copyright © 2023 Syd Polk

"""

import datetime
import json
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
    default_aac_6ch_layout = None
    default_aac_5ch_layout = None

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
        self.default_aac_5ch_layout = os.environ.get('H265_AAC_5CH_LAYOUT', '5.0')
        self.default_aac_6ch_layout = os.environ.get('H265_AAC_6CH_LAYOUT', '5.1(side)')
        time_str = strftime('%Y%m%d%H%M%S', localtime())
        self.log_name = f'h265Converter-{time_str}.log'

    def run_ffmpeg(self, command, tmp_path, phase):
        """
        Run ffmpeg with a unique report file for each invocation so logs are not overwritten.
        """
        time_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        log_file = tmp_path.joinpath(f'h265Converter-{time_str}-{phase}.log')
        my_env = os.environ.copy()
        my_env["FFREPORT"] = f'file={log_file}:level=32'
        output = subprocess.run(command, stderr=subprocess.DEVNULL, env=my_env)
        return output, log_file

    def run_audio_probe(self, src_file, force_ts_demux=False):
        probe_command = ['ffprobe', '-v', 'error']
        if force_ts_demux:
            probe_command.extend([
                '-f', 'mpegts',
                '-analyzeduration', '100M',
                '-probesize', '100M'
            ])
        probe_command.extend([
            '-select_streams', 'a:0',
            '-show_entries', 'stream=channels,channel_layout',
            '-of', 'json',
            src_file
        ])
        return subprocess.run(probe_command, capture_output=True, text=True)

    def detect_audio_layout(self, src_file):
        """
        Determine the primary audio stream layout so AAC gets a valid channel layout.
        Returns None when no audio stream is present.
        """
        result = self.run_audio_probe(src_file)
        if result.returncode != 0 and Path(src_file).suffix.lower() in {'.ts', '.m2ts'}:
            result = self.run_audio_probe(src_file, force_ts_demux=True)
        if result.returncode != 0:
            return None

        try:
            probe_data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

        streams = probe_data.get('streams', [])
        if len(streams) == 0:
            return None

        stream = streams[0]
        channels = stream.get('channels')
        channel_layout = stream.get('channel_layout')
        if channel_layout and channel_layout != 'unknown':
            return channel_layout

        if channels == 5:
            return self.default_aac_5ch_layout

        if channels == 6:
            return self.default_aac_6ch_layout

        return None

    def build_encode_command(self, src_file, tmp_file, force_ts_demux=False):
        input_options = self.build_input_options(src_file, force_ts_demux)
        audio_layout = self.detect_audio_layout(src_file.as_posix())
        command = ['ffmpeg', self.overwrite_flag, '-report']
        command.extend(input_options)
        command.extend(['-i', src_file, '-c:v', 'libx265', '-c:a', 'aac'])
        if audio_layout is not None:
            command.extend(['-channel_layout', audio_layout])
        command.extend(['-tag:v', 'hvc1', tmp_file])
        return command

    def build_input_options(self, src_file, force_ts_demux=False):
        """
        Use more tolerant demux/decode options for transport streams so corruption
        does not cause ffmpeg to abort too early.
        """
        ts_suffixes = {'.ts', '.m2ts'}
        if src_file.suffix.lower() not in ts_suffixes:
            return []
        input_options = [
            '-fflags', '+genpts+discardcorrupt',
            '-err_detect', 'ignore_err',
            '-max_error_rate', '1'
        ]
        if force_ts_demux:
            input_options.extend(['-f', 'mpegts'])
        return input_options

    def is_transport_stream(self, src_file):
        return src_file.suffix.lower() in {'.ts', '.m2ts'}

    def is_unreadable_transport_stream(self, log_file):
        if log_file is None or not log_file.exists():
            return False
        try:
            report = log_file.read_text(errors='ignore')
        except OSError:
            return False

        unreadable_markers = [
            'Error opening input file',
            'Error opening input files:',
            'could not find codec parameters',
            'Could not detect TS packet size',
            'Invalid data found when processing input'
        ]
        for marker in unreadable_markers:
            if marker in report:
                return True
        return False

    def build_salvage_name(self, video):
        time_str = strftime('%Y%m%d%H%M%S', localtime())
        base_name = video.stem.replace(" ", "")
        return f".{base_name}{time_str}.salvage.ts"

    def try_salvage_remux(self, src_file, tmp_path):
        salvage_file = tmp_path.joinpath(self.build_salvage_name(src_file))
        print(f'{datetime.datetime.now()}: Initial encode failed; attempting salvage remux to {salvage_file}...')
        salvage_file.unlink(missing_ok=True)
        salvage_command = ['ffmpeg', self.overwrite_flag, '-report']
        salvage_command.extend(self.build_input_options(src_file))
        salvage_command.extend([
            '-i', src_file,
            '-map', '0:v:0?',
            '-map', '0:a:0?',
            '-c', 'copy',
            '-f', 'mpegts',
            salvage_file
        ])
        output, log_file = self.run_ffmpeg(salvage_command, tmp_path, 'salvage')
        if output.returncode != 0 and src_file.suffix.lower() in {'.ts', '.m2ts'}:
            salvage_file.unlink(missing_ok=True)
            salvage_command = ['ffmpeg', self.overwrite_flag, '-report']
            salvage_command.extend(self.build_input_options(src_file, force_ts_demux=True))
            salvage_command.extend([
                '-i', src_file,
                '-map', '0:v:0?',
                '-map', '0:a:0?',
                '-c', 'copy',
                '-f', 'mpegts',
                salvage_file
            ])
            output, log_file = self.run_ffmpeg(salvage_command, tmp_path, 'salvage-tsdemux')
        if output.returncode != 0:
            salvage_file.unlink(missing_ok=True)
            return None, log_file
        if not salvage_file.exists() or salvage_file.stat().st_size == 0:
            salvage_file.unlink(missing_ok=True)
            return None, log_file
        return salvage_file, log_file

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
        if str(src_file).lower().endswith('.h265.mp4'):
            print(f'{datetime.datetime.now()}: Skipping prior converted file {src_file}.')
            return True

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

        command = self.build_encode_command(src_file, tmp_file)

        if not self.dry_run:
            start = datetime.datetime.now()

            tmp_path.mkdir(parents=True, exist_ok=True)

            print(f'{start}: Converting {src_file} to {tmp_file}...')
            output, log_file = self.run_ffmpeg(command, tmp_path, 'encode')
            if output.returncode != 0 and self.is_transport_stream(src_file):
                tmp_file.unlink(missing_ok=True)
                command = self.build_encode_command(src_file, tmp_file, force_ts_demux=True)
                output, log_file = self.run_ffmpeg(command, tmp_path, 'encode-tsdemux')
            salvage_file = None
            if output.returncode != 0:
                salvage_file, log_file = self.try_salvage_remux(src_file, tmp_path)
                if salvage_file is not None:
                    tmp_file.unlink(missing_ok=True)
                    salvage_command = self.build_encode_command(salvage_file, tmp_file)
                    print(f'{datetime.datetime.now()}: Retrying encode from salvage remux...')
                    output, log_file = self.run_ffmpeg(salvage_command, tmp_path, 'encode-salvage')
            end = datetime.datetime.now()
            duration = end - start

            if output.returncode == 0:
                if (not tmp_file.exists()) or tmp_file.stat().st_size == 0:
                    self.error_output(f'{end}: Problem converting {src_file} to {tmp_file}; output file is empty.')
                    if self.tmp_dir is not None:
                        tmp_file.unlink(missing_ok=True)
                        backup_logfile = tmp_file.parent.joinpath(src_file.name).with_suffix('.err')
                        shutil.copyfile(log_file.as_posix(), backup_logfile)
                    if salvage_file is not None:
                        salvage_file.unlink(missing_ok=True)
                    return False
                dest_path.mkdir(parents=True, exist_ok=True)
                print(f'{end}: Wrote {self.size_string(tmp_file.stat().st_size)}.')
                if self.tmp_dir:
                    print(f"{datetime.datetime.now()}: Moving {tmp_file} to {dest_file}.")
                    shutil.move(tmp_file.as_posix(), dest_file.as_posix())
                if not self.preserve_source:
                    src_file.unlink()
                if salvage_file is not None:
                    salvage_file.unlink(missing_ok=True)
            else:
                self.error_output(f'{end}: Problem converting {src_file} to {tmp_file}')
                if self.tmp_dir is not None:
                    tmp_file.unlink(missing_ok=True)
                    backup_logfile = tmp_file.parent.joinpath(src_file.name).with_suffix('.err')
                    shutil.copyfile(log_file.as_posix(), backup_logfile)
                if self.is_transport_stream(src_file) and self.is_unreadable_transport_stream(log_file):
                    print(f'{datetime.datetime.now()}: Removing unreadable transport stream {src_file}.')
                    src_file.unlink(missing_ok=True)
                if salvage_file is not None:
                    salvage_file.unlink(missing_ok=True)
                return False
            print(f"{datetime.datetime.now()}: Time: ", end="")
            self.pretty_print_duration(duration)

        return True

    def convert_videos(self, files, dest=None):
        for file in files:
            print(f'{datetime.datetime.now()}: Converting {file}...')

            self.convert_video(file, dest)

        print('{datetime.datetime.now()}: Done.')
