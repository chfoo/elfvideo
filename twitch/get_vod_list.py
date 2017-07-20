import argparse
import json
import logging
import os
import random
import urllib.parse
import time

import requests

CLIENT_ID = 'FILL_ME_IN_HERE'

URL_TEMPLATE = 'https://api.twitch.tv/kraken/channels/56648155/videos?client_id={client_id}&api_version=5&limit=100&offset={offset}'


_logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.DEBUG)

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('out_dir')

    args = arg_parser.parse_args()

    counter = 0
    while True:
        _logger.info("Counter=%s", counter)

        for attempt in range(5):
            try:
                response = requests.get(URL_TEMPLATE.format(offset=counter, client_id=CLIENT_ID))
            except requests.RequestException:
                _logger.exception("Request error")
                time.sleep(10)
            else:
                doc = response.json()
                break
        else:
            raise Exception("API fetch error")

        assert isinstance(doc, dict), doc

        if "videos" in doc:
            video_list = doc["videos"]
        else:
            _logger.debug('%s', doc)
            raise Exception("No videos")

        if len(video_list) == 0:
            break

        for item in video_list:
            video_id = item['_id']

            _logger.debug('Writing %s', video_id)

            path = os.path.join(args.out_dir, urllib.parse.quote(video_id, '') + '.json')

            with open(path, 'w') as file:
                file.write(json.dumps(item))

        counter += len(video_list)

        time.sleep(random.uniform(3, 10))

    _logger.info('Done')


if __name__ == '__main__':
    main()
