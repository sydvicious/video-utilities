#!/usr/bin/env python3

import h265Converer
import argparse

from pathlib import Path

parser = argparse.ArgumentParser(description="Convert video files to libx265 mp4 files using ffmpeg",
                                 prog="covert_video",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                 fromfile_prefix_chars='@')
parser.add_argument('files', type=str, nargs='+',
                    help=
                    '''
                    Files to convert. 
                    ''')
parser.add_argument('--continue', '-f', action='store_true', dest='force',
                    help=
                    '''
                    Don't stop processing if a file gives an error; try the next file in the list.
                    ''')
parser.add_argument('--destination', '-o', nargs=1,
                    help=
                    '''
                    The destination file or directory that the result will be written to. This has similar semantics
                    to the unix 'cp' command. There are a few forms of this.
                    <source_file> --destination <existing_file.mp4> - If the --overwrite flag is set, existing_file.mp4
                    will be overwritten by the new file; otherwise, this is an error, and continued execution is 
                    controlled by the --continue flag.
                    <source_file> --destination <existing_file> - Like above, but '.mp4' will be appended to 
                    'existing_file'.
                    <source_file> --destination <non_existing_name (with no trailing slash) - non_existing_name will be 
                    treated as the destination file name, with the extension '.mp4' appended.

                    <source_file1> [<source_file2>...] --destination <existing_directory> - All destination files will
                    be written into the 'existing_directory'. Any trailing slashes in the 'existing_directory' argument
                    will be stripped all of the source files will be changed to '.mp4'. 
                    <source_file1> [<source_file2>...] --destination <non-existing + '/'> - A directory with the name
                    of 'non-existing' will be created and destination files will be written into it. All extensions of
                    the source files will be changed to '.mp4'.

                    For now, any directory entries in the source list will be skipped.

                    TBD: Create missing subdirectories
                    TBD: Recursive traversal and creation of destination directories

                    Without the --destination setting, all files will be converted in the directories in which
                    they reside, subject to the --overwrite and --continue flags.
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
parser.add_argument('--suffix', '-s', nargs=1,default='.h265.mp4',
                    help=
                    '''
                    Use this extension for the final file.
                    ''')
parser.add_argument('--tmp-dir', '--tmp', '-t', nargs=1,
                    help=
                    '''
                    Directory where the converted file will be created. After the conversion is done, the file will be
                    moved to the destination directory.
                    ''')
args = parser.parse_args()

converter = h265Converer.H265Converter(args.files, args.suffix, args.overwrite, args.force, args.dry_run, args.destination,
                                       args.tmp_dir, args.preserve_source)
converter.convert_videos()

