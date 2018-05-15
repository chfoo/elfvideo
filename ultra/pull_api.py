import argparse
import json
import re
import sqlite3
import time
import logging

import requests

URL_TEMPLATE = 'https://twitchplayspokemon.tv/api/sidegame_inputs?sort=timestamp&filter:id.game=ultra&limit=100&skip={skip}'

_logger = logging.getLogger(__name__)


def main():
    logging.basicConfig(level=logging.INFO)

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('database')

    args = arg_parser.parse_args()

    db_path = args.database

    db = sqlite3.connect(db_path)

    with db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS pmd_inputs (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            input TEXT NOT NULL,
            voters TEXT,
            imgur_id TEXT
        )
        ''')
        db.execute('PRAGMA journal_mode = WAL')
        db.execute('PRAGMA synchronous = NORMAL')

    row = db.execute('SELECT max(id) FROM pmd_inputs').fetchone()

    if row and row[0]:
        counter = row[0]
    else:
        counter = 0

    while True:
        _logger.info("Counter=%s", counter)

        for attempt in range(5):
            try:
                response = requests.get(URL_TEMPLATE.format(skip=counter))
            except requests.RequestException:
                _logger.exception("Request error")
                time.sleep(10)
            else:
                doc = response.json()
                break
        else:
            raise Exception("API fetch error")

        assert isinstance(doc, list), doc

        if len(doc) == 0:
            break

        values = []

        for item in doc:
            try:
                row_id = item['id']['position']
                date = item['timestamp']
                winning_input = item['winning_input']
                voters = json.dumps(item['voters'])
                imgur_id = item.get('imgur_screenshot_id')

                if re.match(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d\d\d000$', date):
                    date = date[:-3]

                assert re.match(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(\.\d\d\d)?$', date), date
                assert isinstance(row_id, int)

                values.append((row_id, date, winning_input, voters, imgur_id))
            except Exception:
                _logger.exception('felkcraft BabyRage item=%s', item)
                raise

        with db:
            db.executemany(
                '''INSERT INTO pmd_inputs (
                id, date, input, voters, imgur_id
                ) VALUES (?, ?, ?, ?, ?)
                ''', values)

        counter += len(doc)

    _logger.info('Done')


if __name__ == '__main__':
    main()
