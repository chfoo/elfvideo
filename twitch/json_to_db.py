import argparse
import glob
import json
import logging

import sqlite3


def main():
    logging.basicConfig(level=logging.DEBUG)

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('json_dir')
    arg_parser.add_argument('database')

    args = arg_parser.parse_args()

    db = sqlite3.connect(args.database)

    with db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS vods (
            id INTEGER PRIMARY KEY,
            recorded_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            length INTEGER NOT NULL,
            published_at TEXT NOT NULL,
            title TEXT NOT NULL,
            broadcast_type TEXT NOT NULL,
            views INTEGER NOT NULL
        )
        ''')
        db.execute('PRAGMA journal_mode = WAL')
        db.execute('PRAGMA synchronous = NORMAL')

    for name in glob.glob(args.json_dir + '/*.json'):
        with open(name) as file:
            doc = json.load(file)

        with db:
            db.execute(
                '''
                INSERT into vods 
                (id, recorded_at, created_at, length, published_at, title,
                broadcast_type, views)
                VALUES
                (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    int(doc['_id'].strip('v')),
                    doc['recorded_at'],
                    doc['created_at'],
                    doc['length'],
                    doc['published_at'],
                    doc['title'],
                    doc['broadcast_type'],
                    doc['views']
                )
            )


if __name__ == '__main__':
    main()
