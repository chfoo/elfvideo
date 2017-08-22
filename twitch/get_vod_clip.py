import argparse
import datetime
import os
import re
import sqlite3
import subprocess

import arrow
import requests


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('vod_database')
    arg_parser.add_argument('date')
    arg_parser.add_argument('output_name')
    arg_parser.add_argument('--cache-dir', default='/tmp/get_vod_clip/')

    args = arg_parser.parse_args()

    os.makedirs(args.cache_dir, exist_ok=True)

    database = sqlite3.connect(args.vod_database)

    datetime_obj = arrow.get(args.date)

    print('Getting VOD ID from database')

    row = database.execute('''
        SELECT id, recorded_at, length
        FROM vods
        WHERE recorded_at < ?
        ORDER BY recorded_at DESC
        LIMIT 1 
    ''', (datetime_obj.isoformat(),)).fetchone()

    print('\t', row)

    offset = datetime_obj - arrow.get(row[1])

    minutes, seconds = divmod(int(offset.total_seconds()), 60)
    hours, minutes = divmod(minutes, 60)
    web_url = 'https://www.twitch.tv/videos/{}?t={}h{}m{}s'.format(
        row[0],
        hours, minutes, seconds
    )
    print('\t', web_url)

    video_id = row[0]
    playlist_path = os.path.join(args.cache_dir, str(video_id))
    playlist_url_path = os.path.join(args.cache_dir, str(video_id) + '_url')

    if os.path.exists(playlist_path):
        print('Using cached playlist')

        with open(playlist_path) as file:
            playlist = file.read()

        with open(playlist_url_path) as file:
            playlist_url = file.read()
    else:
        print('Getting VOD url')

        playlist_url = subprocess.check_output([
            'youtube-dl', '--get-url',
            'https://www.twitch.tv/videos/{}'.format(row[0])
        ]).decode('utf8').strip()

        print('\t', playlist_url)

        print('Download playlist')

        response = requests.get(playlist_url)
        response.raise_for_status()

        playlist = response.content.decode('utf8', 'replace')

        print('\t Size', len(playlist))

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
            # print('\t', 'Found start time', start_time)
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

                print('Found segment URL', segment_url)
                print('\t', current_time, datetime_obj, segment_end_time)
                break

            duration += segment_duration
            segment_duration = None
            # print('\t', current_time)
            # print('\t', duration)

    print('Downloading')

    response = requests.get(segment_url)
    response.raise_for_status()

    with open(args.output_name, 'wb') as file:
        for data in response.iter_content(4096):
            file.write(data)

    print('Done')


if __name__ == '__main__':
    main()
