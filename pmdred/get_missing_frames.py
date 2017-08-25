import argparse
import datetime
import logging
import os
import re
import sqlite3
import subprocess
import sys

import PIL.Image
import arrow
import arrow.parser

_logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('image_dir')
    arg_parser.add_argument('input_database')
    arg_parser.add_argument('vod_database')
    arg_parser.add_argument(
        '--tesseract-data-dir',
        default='tppocr/tessdata/'
    )
    arg_parser.add_argument(
        '--tesseract-language',
        default='pkmngba_en'
    )
    arg_parser.add_argument(
        '--tesseract-digits',
        default='/usr/share/tesseract-ocr/tessdata/configs/digits'
    )

    args = arg_parser.parse_args()

    missing_path = os.path.join(args.image_dir, 'missing.txt')

    inputs_db = sqlite3.connect(args.input_database)
    vods_db = sqlite3.connect(args.vod_database)

    _logger.info('Loading')

    missing_frames = []

    with open(missing_path) as file:
        for line in file:
            missing_frames.append(int(line.strip()))

    delta = None
    old_delta = None

    for frame in missing_frames:
        sub_dir_name = '{:02d}'.format(frame // 1000)
        image_path = os.path.join(args.image_dir, sub_dir_name, '{:05d}.v.png'.format(frame))

        os.makedirs(os.path.join(args.image_dir, 'ts', sub_dir_name), exist_ok=True)
        transport_file = os.path.join(args.image_dir, 'ts', sub_dir_name, '{:05d}.ts'.format(frame))

        _logger.info('Getting missing frame {}'.format(frame))

        row = inputs_db.execute('''
            SELECT date FROM pmd_inputs WHERE id = ? LIMIT 1
        ''', (frame,)).fetchone()

        date_str = row[0]
        target_date = arrow.get(date_str)
        target_date += datetime.timedelta(seconds=4)  # adjust for countdown timer

        _logger.info('  %s %s', date_str, target_date)

        if not os.path.exists(transport_file):
            try:
                subprocess.check_call([
                    sys.executable,
                    os.path.join(
                        os.path.dirname(__file__),
                        '..', 'twitch', 'get_vod_clip.py'
                    ),
                    args.vod_database,
                    target_date.isoformat(),
                    transport_file
                ])
            except subprocess.CalledProcessError as error:
                if error.returncode == 14:
                    _logger.warning('***Could not get a segment for frame %s***', frame)
                    continue
                else:
                    raise

        if os.path.getsize(transport_file) == 0:
            _logger.warning('***Segment was 0 sized for frame %s***', frame)
            continue

        frame_file = transport_file + '.png'
        timestamp_image_path = transport_file + '_crop.png'

        if not os.path.exists(frame_file):
            _logger.info('Extracting frame')

            subprocess.check_call([
                'ffmpeg',
                '-i', transport_file, '-vframes', '1', frame_file,
                '-v', 'warning', '-y'
            ])

            _logger.info('Cropping date time')

            image = PIL.Image.open(frame_file)
            cropped_image = image.crop((
                int(image.width * 165 / 1920),
                int(image.height * 1040 / 1080),
                int(image.width * 442 / 1920),
                int(image.height * 1075 / 1080),
            ))
            cropped_image.save(timestamp_image_path)

        _logger.info('Getting date')

        result = subprocess.check_output([
            'tesseract', '--tessdata-dir', args.tesseract_data_dir,
            '-l', args.tesseract_language,
            timestamp_image_path, 'stdout',
            args.tesseract_digits
        ]).decode('utf-8').strip()

        _logger.info('  %s', result)

        match = re.search(r'(\d{4}).(\d\d).(\d\d).(\d\d).(\d\d).(\d\d)', result)

        if match:
            try:
                ocr_date = arrow.get('{}-{}-{}T{}:{}:{}'.format(
                    match.group(1),
                    match.group(2),
                    match.group(3),
                    match.group(4),
                    match.group(5),
                    match.group(6),
                ))
            except arrow.parser.ParserError as error:
                _logger.warning('***Could not get a date for frame %s***', frame)
                continue

            _logger.info('  %s', ocr_date)

            old_delta = delta
            delta = target_date - ocr_date
        elif delta is not None:
            _logger.warning('Could not get a date for frame %s. Using old delta', frame)
        else:
            _logger.warning('***Could not get a date for frame %s***', frame)
            continue

        if delta.total_seconds() > 120:
            delta = old_delta
            _logger.warning('***Date delta too high frame %s***', frame)
            continue

        if os.path.exists(image_path):
            continue

        new_date = target_date + delta

        _logger.info('  Delta: %s  New date: %s', delta, new_date)

        if delta.total_seconds() >= 2:
            transport_file = os.path.join(
                args.image_dir,
                'ts',
                '{}_cor_{}.ts'.format(frame, int(delta.total_seconds()))
            )

            if not os.path.exists(transport_file):
                _logger.info('Getting corrected frame')

                try:
                    subprocess.check_call([
                        sys.executable,
                        os.path.join(
                            os.path.dirname(__file__),
                            '..', 'twitch', 'get_vod_clip.py'
                        ),
                        args.vod_database,
                        new_date.isoformat(),
                        transport_file
                    ])
                except subprocess.CalledProcessError as error:
                    if error.returncode == 14:
                        _logger.warning('***Could not get a segment for frame %s***', frame)
                        continue
                    else:
                        raise

        if os.path.getsize(transport_file) == 0:
            _logger.warning('***Segment part 2 was 0 sized for frame %s***', frame)
            continue

        frame_file = transport_file + '.png'

        subprocess.check_call([
            'ffmpeg',
            '-i', transport_file, '-vframes', '1', frame_file,
            '-v', 'warning', '-y'
        ])

        _logger.info('Cropping frame')

        if 22046 <= frame <= 25327:
            image = PIL.Image.open(frame_file)
            cropped_image = image.crop((
                int(image.width * 727 / 1920),
                int(image.height * 286 / 1080),
                int(image.width * (727 + 956) / 1920),
                int(image.height * (286 + 640) / 1080),
            ))
            cropped_image = cropped_image.resize((240, 160))
            cropped_image.save(image_path)
        else:
            image = PIL.Image.open(frame_file)
            cropped_image = image.crop((
                int(image.width * 1676 / 1920),
                int(image.height * 916 / 1080),
                int(image.width * 1916 / 1920),
                int(image.height * 1076 / 1080),
            ))
            cropped_image.save(image_path)

    _logger.info('Done!')


if __name__ == '__main__':
    main()
