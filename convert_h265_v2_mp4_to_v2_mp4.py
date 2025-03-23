#!/usr/bin/env python3

"""

Copyright © 2025 Syd Polk

"""

import argparse
import os

parser = argparse.ArgumentParser(description="Recursively rename files with extension .h265.v2.mp4 to .v2.mp4",
                                 prog="convert_h265_v2_mp4_to_v2_mp4",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument('dir', type=str,
                    help=
                    '''
                    Directory to traverse. 
                    ''')

args = parser.parse_args()

for top, dirs, files in os.walk(args.dir):
    for filename in files:
        if filename.endswith(".h265.v2.mp4"):
            old_path = os.path.join(top, filename)
            new_filename = filename.replace(".h265.v2.mp4", ".v2.mp4")
            new_path = os.path.join(top, new_filename)

            print(f"Renaming:\n  From: {old_path}\n  To:   {new_path}")
            os.rename(old_path, new_path)


