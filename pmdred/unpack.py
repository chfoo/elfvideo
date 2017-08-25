import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess

ARCHIVE_SHA1_HASH = 'b16d113adfedd23739af27a9a6bd8e48236c4343'


def check_archive(filename):
    hasher = hashlib.sha1()
    with open(filename, 'rb') as file:
        while True:
            data = file.read(4096)
            if not data:
                break
            hasher.update(data)

    if hasher.hexdigest().lower() != ARCHIVE_SHA1_HASH.lower():
        raise Exception(
            'Archive file hash does not match the one Felkcraft has released.'
        )


class CustomJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()

        return json.JSONEncoder.default(self, o)


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('input_archive')
    arg_parser.add_argument('output_dir')

    args = arg_parser.parse_args()

    print('Checking archive')
    check_archive(args.input_archive)

    print('Reading archive listing')
    # Important: Force 7zip to display in UTC using environment variable
    output = subprocess.check_output(
        ['7z', 'l', args.input_archive, '-slt', '-ba'],
        env={'TZ': ''}
    )

    infos = []
    info = {}

    for line in output.splitlines(keepends=False):
        line = line.decode()

        if line.startswith('Path = '):
            info['path'] = line[7:]

        elif line.startswith('Modified = '):
            info['modified'] = datetime.datetime.strptime(line[11:],
                                                          '%Y-%m-%d %H:%M:%S')
        elif not line:
            assert 'path' in info, info
            assert 'modified' in info, info

            if info['path'].endswith('.png'):
                info['index'] = int(
                    re.match(r'pmdrrt/pmdrrt-(\d+)\.png', info['path']).group(1)
                )

                infos.append(info)

            info = {}

    print('Extracting')

    subprocess.check_call(['7z', 'e', args.input_archive,
                           '-o{}'.format(args.output_dir)])

    print('Renaming')

    for index, info in enumerate(infos):
        filename = os.path.basename(info['path'])

        os.rename(
            os.path.join(args.output_dir, filename),
            os.path.join(args.output_dir, '{:05d}.png'.format(info['index']))
        )

    print('Writing metadata')

    path = os.path.join(args.output_dir, 'archive.json')
    with open(path, 'w') as file:
        json.dump(infos, file, indent=4, sort_keys=True, cls=CustomJSONEncoder)

    frame_indexes = frozenset(info['index'] for info in infos)
    max_frame = max(frame_indexes)

    path = os.path.join(args.output_dir, 'missing.txt')
    with open(path, 'w') as file:
        for index in range(1, max_frame + 1):
            if index not in frame_indexes:
                file.write('{}\n'.format(index))

    print('Done')

if __name__ == '__main__':
    main()
