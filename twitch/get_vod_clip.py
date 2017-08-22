import argparse
import datetime
import logging
import os
import re
import sqlite3
import subprocess

import arrow
import requests

_logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('vod_database')
    arg_parser.add_argument('date')
    arg_parser.add_argument('output_name')
    arg_parser.add_argument('--cache-dir', default='/tmp/get_vod_clip/')

    args = arg_parser.parse_args()

    os.makedirs(args.cache_dir, exist_ok=True)

    database = sqlite3.connect(args.vod_database)

    datetime_obj = arrow.get(args.date)

    _logger.info('Getting VOD ID from database')

    row = database.execute('''
        SELECT id, recorded_at, length
        FROM vods
        WHERE recorded_at < ?
        ORDER BY recorded_at DESC
        LIMIT 1 
    ''', (datetime_obj.isoformat(),)).fetchone()

    _logger.info('  %s', row)

    offset = datetime_obj - arrow.get(row[1])

    minutes, seconds = divmod(int(offset.total_seconds()), 60)
    hours, minutes = divmod(minutes, 60)
    web_url = 'https://www.twitch.tv/videos/{}?t={}h{}m{}s'.format(
        row[0],
        hours, minutes, seconds
    )
    _logger.info('  %s', web_url)

    video_id = row[0]
    playlist_path = os.path.join(args.cache_dir, str(video_id))
    playlist_url_path = os.path.join(args.cache_dir, str(video_id) + '_url')

    if os.path.exists(playlist_path):
        _logger.info('Using cached playlist')

        with open(playlist_path) as file:
            playlist = file.read()

        with open(playlist_url_path) as file:
            playlist_url = file.read()
    else:
        _logger.info('Getting VOD url')

        playlist_url = subprocess.check_output([
            'youtube-dl', '--get-url',
            'https://www.twitch.tv/videos/{}'.format(row[0])
        ]).decode('utf8').strip()

        _logger.info('  %s', playlist_url)

        _logger.info('Download playlist')

        response = requests.get(playlist_url)
        response.raise_for_status()

        playlist = response.content.decode('utf8', 'replace')

        _logger.info('  Size %s', len(playlist))

        with open(playlist_path, 'w') as file:
            file.write(playlist)

        with open(playlist_url_path, 'w') as file:
            file.write(playlist_url)

    start_time = arrow.get(row[1])
    # start_time = None
    duration = 0.0
    segment_duration = None
    segment_url = None

    for line in playlist.splitlines():
        line = line.strip()

        if line.startswith('#ID3-EQUIV-TDTG'):
            pass
            # start_time = arrow.get(line[15:])
            # _logger.info('  Found start time %s', start_time)
        elif line.startswith('#EXTINF:'):
            assert segment_duration is None, segment_duration
            segment_duration = float(
                re.match(r'#EXTINF:(\d+\.\d+)', line).group(1)
            )
        elif line.startswith('#') or not line:
            continue
        else:
            assert segment_duration is not None
            segment_filename = line
            current_time = start_time + datetime.timedelta(seconds=duration)
            segment_end_time = current_time \
                + datetime.timedelta(seconds=segment_duration)

            if current_time <= datetime_obj \
                    and datetime_obj <= segment_end_time:
                segment_url = '{}/{}'.format(
                    playlist_url.rsplit('/', 1)[0], segment_filename
                )

                _logger.info('Found segment URL %s', segment_url)
                _logger.info('  %s %s %s', current_time, datetime_obj, segment_end_time)
                break

            duration += segment_duration
            segment_duration = None
            # _logger.info('  %s', current_time)
            # _logger.info('  %s', duration)

    _logger.info('Downloading')

    response = requests.get(segment_url)
    response.raise_for_status()

    with open(args.output_name, 'wb') as file:
        for data in response.iter_content(4096):
            file.write(data)

    _logger.info('Done')


if __name__ == '__main__':
    main()
