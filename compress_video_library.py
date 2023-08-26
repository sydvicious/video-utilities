#!/usr/bin/env python3

"""

Copyright © 2023 Syd Polk

"""


import TreeTraverser
import argparse


def check_positive(value):
    ivalue = int(value)
    if ivalue < 0:
        raise argparse.ArgumentTypeError("%s is an invalid non-negative int value" % value)
    return ivalue


parser = argparse.ArgumentParser(description="Convert video files to libx265 mp4 files using ffmpeg",
                                 prog="compress_video_library",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                 fromfile_prefix_chars='@')
parser.add_argument('source', type=str,
                    help=
                    '''
                    Root directory to start traversing. 
                    ''')
parser.add_argument('--continue', '-f', action='store_true', dest='force',
                    help=
                    '''
                    Don't stop processing if a file gives an error; try the next file in the list.
                    ''')
parser.add_argument('--destination', '--dest', '-d',
                    help=
                    '''
                    Target directory. Preserves directory structure, creating new directories as needed.
                    ''')
parser.add_argument('--dry-run', '-n', action='store_true',
                    help=
                    '''
                    Generate the commands that would be executed, and output them to stdout, but do not execute them.
                    ''')
parser.add_argument('--overwrite', '-w', action='store_true',
                    help=
                    '''
                    Normally, if the destination file exists, the system will not do the conversion,
                    and either stop processing or continue to the next file, depending on the --continue
                    flag. This option will overwrite the new file. Note that it destroys the destination
                    file immediately.
                    ''')
parser.add_argument('--preserve-source', '-p', action='store_true',
                    help=
                    '''
                    Don't delete source files after conversion.
                    ''')
parser.add_argument('--start-time', '-$', type=str,
                    help=
                    '''
                    Only start encoding after this time. If no stop_time is specified,
                    end time is midnight. If start_time > end_time, the time range
                    will span midnight, and a job will start after the end_time on one
                    day, and won't start after start_time on the next day.
                    ''')
parser.add_argument('--stop-time', '--end-time', '-^', type=str,
                    help=
                    '''
                    Only start encoding before this time. If no start_time is specified,
                    start time is midnight. If start_time > end_time, the time range
                    will span midnight, and a job will start after the end_time on one
                    day, and won't start after start_time on the next day.
                    ''')
parser.add_argument('--stop-when-complete', '-x', action='store_true',
                    help=
                    '''
                    Stop after one complete pass through the tree. This is not the default, as this is designed
                    to be a file system watch dog.
                    ''')
parser.add_argument('--suffix', '-s', nargs=1, default='.h265.mp4',
                    help=
                    '''
                    Use this extension for the final file.
                    ''')
parser.add_argument('--tmp-dir', '--tmp', '-t',
                    help=
                    '''
                    Directory where the converted file will be created. After the conversion is done, the file will be
                    moved to the destination directory.
                    ''')
parser.add_argument('--error-list-file', '-e',
                    help=
                    '''
                    When specified, any files that can't be converted are added to this list, and at start up,
                    this file is read, and any files listed won't be put into the queue.
                    ''')
parser.add_argument('--refresh', '-g', type=check_positive, nargs=1, default=3600,
                    help=
                    '''
                    Refresh file tree every specified interval in seconds. Default is 1 day. Setting this very low
                    will cause a scan of the source after every single conversion. For a local drive, that's no big
                    deal. For a network drive, you might not want to mess with that.
                    ''')
parser.add_argument('--skip-newer', action='store_true', dest='skip_newer',
                    help=
                    '''
                    If a file is less than 24 hours, skip it. This is so that if Plex is recording a file,
                    we don't try to encode an incomplete recording.
                    ''')
args = parser.parse_args()

traverser = TreeTraverser.TreeTraverser(args.suffix, args.overwrite, args.force, args.dry_run, args.tmp_dir,
                                        args.preserve_source, args.start_time, args.stop_time, args.stop_when_complete,
                                        args.refresh, args.error_list_file, args.skip_newer)
traverser.traverse(args.source, args.destination)
