"""Script to generate TwitchPlaysPokemon PMD timelapse compilation video"""
# Copyright 2017 By Christopher Foo. License: MIT.

import argparse
import concurrent.futures
import datetime
import itertools
import logging
import multiprocessing
import os
import sqlite3
import typing
from itertools import zip_longest
from typing import List, Optional

import arrow
import cairo


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def main():
    logging.basicConfig(level=logging.INFO)

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('images_dir')
    arg_parser.add_argument('output_dir')
    arg_parser.add_argument('--skip-exists', action='store_true')
    arg_parser.add_argument('--database', default='inputs.db')

    args = arg_parser.parse_args()

    renderer = Renderer(
        args.images_dir,
        args.output_dir,
        args.database,
        skip_exists=args.skip_exists
    )

    renderer.run()


FPS = 12

FONT_NAME = 'Nimbus Sans L'
FONT_NAME_SYMBOL = 'Symbola'

WIDTH = 1920
HEIGHT = 1080

CROSSFADE_RANGE = (-24, 4)

GAMEBOY_WIDTH = 240
GAMEBOY_HEIGHT = 160

OUTPUT_SCREENSHOT_WIDTH = GAMEBOY_WIDTH * 5
SCREENSHOT_PADDING = 30
SCREENSHOT_SCALE = OUTPUT_SCREENSHOT_WIDTH / GAMEBOY_WIDTH
OUTPUT_SCREENSHOT_HEIGHT = GAMEBOY_HEIGHT * SCREENSHOT_SCALE

TITLE_TEXT_SIZE = 55
TITLE_Y = SCREENSHOT_PADDING + TITLE_TEXT_SIZE

SCREENSHOT_X = SCREENSHOT_PADDING
SCREENSHOT_Y = TITLE_Y + SCREENSHOT_PADDING * 2

SIDE_BAR_LEFT = SCREENSHOT_PADDING + GAMEBOY_WIDTH * SCREENSHOT_SCALE + SCREENSHOT_PADDING
SIDEBAR_SCREENSHOT_SCALE = (WIDTH - SCREENSHOT_PADDING - SIDE_BAR_LEFT) / GAMEBOY_WIDTH
SIDEBAR_SCREENSHOT_X = SIDE_BAR_LEFT
SIDEBAR_SCREENSHOT_Y = SCREENSHOT_Y + OUTPUT_SCREENSHOT_HEIGHT - GAMEBOY_HEIGHT * SIDEBAR_SCREENSHOT_SCALE

DATE_TEXT_SIZE = 50
DATE_Y = SCREENSHOT_Y + DATE_TEXT_SIZE

DURATION_TEXT_SIZE = 50
DURATION_Y = DATE_Y + SCREENSHOT_PADDING + DURATION_TEXT_SIZE

FRAME_TEXT_SIZE = 50
FRAME_TEXT_Y = DURATION_Y + SCREENSHOT_PADDING + FRAME_TEXT_SIZE

INPUT_VOTE_TEXT_SIZE = 50
INPUT_VOTE_TEXT_Y = FRAME_TEXT_Y + SCREENSHOT_PADDING + INPUT_VOTE_TEXT_SIZE

FrameInfo = typing.NamedTuple('FrameInfo', [
    ('input_id', int),
    ('date', datetime.datetime),
    ('input_vote', str)
])


class Renderer:
    def __init__(self, images_dir: str, output_dir: str, database_filename: str,
                 skip_exists: bool=False):
        self._images_dir = images_dir
        self._output_dir = output_dir
        self._database = sqlite3.connect(database_filename)
        self._skip_exists = skip_exists

        self._frame_infos = []  # type: List[FrameInfo]

    def run(self):
        self._populate_frame_infos()

        input_indexes = tuple(range(len(self._frame_infos)))
        input_indexes = tuple(itertools.chain(
            itertools.repeat(input_indexes[0], FPS),
            input_indexes,
            itertools.repeat(input_indexes[-1], FPS * 5),
        ))
        total_render_frames = len(input_indexes)

        with concurrent.futures.ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            for batch in grouper(enumerate(input_indexes), 100):
                futures = []
                for item in batch:
                    if not item:
                        continue
                    render_index, input_index = item
                    output_filename = os.path.join(self._output_dir, '{:05}.png'.format(render_index))

                    if self._skip_exists and os.path.exists(output_filename):
                        continue

                    futures.append(executor.submit(
                        self._gen_frame,
                        render_index, input_index,
                        output_filename, total_render_frames
                    ))

                for future in concurrent.futures.as_completed(futures):
                    future.result()

    def _populate_frame_infos(self):
        rows = self._database.execute('''
            SELECT id, date, input FROM pmd_inputs ORDER BY ID
        ''')

        for row in rows:
            input_id, date_str, input_vote = row
            date = arrow.get(date_str)

            self._frame_infos.append(FrameInfo(input_id, date, input_vote))

    def _get_image_path(self, frame_id: int) -> Optional[str]:
        for suffix in ('.png', '.v.png'):
            input_path = os.path.join(self._images_dir,
                                      '{:02d}'.format(frame_id // 1000),
                                      '{:05d}{}'.format(frame_id, suffix))

            if os.path.exists(input_path):
                return input_path

    def _gen_frame(self, render_index, input_index, output_filename, total_render_frames):
        num_input_frames = len(self._frame_infos)

        frame_id = input_index + 1

        input_path = self._get_image_path(frame_id)

        if input_path:
            is_vod_screenshot = '.v.' in input_path
        else:
            is_vod_screenshot = False

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, WIDTH, HEIGHT)
        context = cairo.Context(surface)

        context.set_source_rgb(0.0, 0.0, 0.0)
        context.paint()

        context.push_group()

        # Draw title
        context.save()
        context.set_source_rgb(1.0, 1.0, 1.0)
        context.select_font_face(FONT_NAME, cairo.FONT_SLANT_NORMAL,
                                 cairo.FONT_WEIGHT_BOLD)
        context.set_font_size(TITLE_TEXT_SIZE)
        title_x = (WIDTH - SCREENSHOT_PADDING * 2) / 2 - context.get_scaled_font().text_extents('Twitch Plays Pokémon Mystery Dungeon: Red Rescue Team')[2] / 2
        context.move_to(title_x, TITLE_Y)
        context.show_text('Twitch Plays Pokémon Mystery Dungeon: Red Rescue Team')
        context.restore()

        # Draw timestamp
        context.save()
        context.set_source_rgb(1.0, 1.0, 1.0)
        context.set_font_size(DATE_TEXT_SIZE)
        context.move_to(SIDE_BAR_LEFT, DATE_Y)
        date_obj = self._frame_infos[input_index].date
        context.select_font_face(FONT_NAME_SYMBOL)
        context.show_text('📆')
        context.select_font_face(FONT_NAME)
        context.show_text(date_obj.strftime(' %Y-%m-%d %H:%M:%S'))
        context.restore()

        # Draw duration
        context.save()
        context.set_source_rgb(1.0, 1.0, 1.0)
        context.set_font_size(DURATION_TEXT_SIZE)
        context.move_to(SIDE_BAR_LEFT, DURATION_Y)
        first_date_obj = self._frame_infos[0].date
        delta_obj = date_obj - first_date_obj
        days, remainder = divmod(int(delta_obj.total_seconds()), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        context.select_font_face(FONT_NAME_SYMBOL)
        context.show_text('⏱')
        context.select_font_face(FONT_NAME)
        context.show_text(' {days:03}d {hours:02}h {minutes:02}m {seconds:02}s'.format(
            days=days,
            hours=hours,
            minutes=minutes,
            seconds=seconds
        ))
        context.restore()

        # Draw frame counter
        context.save()
        context.set_source_rgb(1.0, 1.0, 1.0)
        context.set_font_size(FRAME_TEXT_SIZE)
        context.move_to(SIDE_BAR_LEFT, FRAME_TEXT_Y)
        context.select_font_face(FONT_NAME_SYMBOL)
        context.show_text('📸')
        context.select_font_face(FONT_NAME)
        context.show_text(' {:05}'.format(input_index + 1))

        if is_vod_screenshot:
            context.show_text('*')

        context.restore()

        # Draw the input vote
        context.save()
        context.set_source_rgb(1.0, 1.0, 1.0)
        context.set_font_size(INPUT_VOTE_TEXT_SIZE)
        context.move_to(SIDE_BAR_LEFT, INPUT_VOTE_TEXT_Y)
        context.select_font_face(FONT_NAME_SYMBOL)
        context.show_text('🎮')
        context.select_font_face(FONT_NAME)
        context.show_text(' {}'.format(self._frame_infos[input_index].input_vote.upper()))
        context.restore()

        # Draw the cross faded image
        for offset in range(CROSSFADE_RANGE[0], CROSSFADE_RANGE[1] + 1):
            sub_index = input_index + offset

            if sub_index < 0 or sub_index >= num_input_frames:
                continue

            sub_frame_id = sub_index + 1
            sub_path = self._get_image_path(sub_frame_id)

            if not sub_path:
                continue

            try:
                sub_input_surface = cairo.ImageSurface.create_from_png(sub_path)
            except OSError:
                logging.exception('Image error on {}'.format(sub_path))
                continue

            context.save()
            context.translate(SIDEBAR_SCREENSHOT_X, SIDEBAR_SCREENSHOT_Y)
            context.scale(SIDEBAR_SCREENSHOT_SCALE, SIDEBAR_SCREENSHOT_SCALE)
            context.set_source_surface(sub_input_surface, 0, 0)
            context.get_source().set_filter(cairo.FILTER_NEAREST)

            if offset < 0:
                weight = 1 - offset / CROSSFADE_RANGE[0]
            elif offset > 0:
                weight = 1 - offset / CROSSFADE_RANGE[1]
            else:
                weight = 1

            weight /= 2

            context.paint_with_alpha(weight)
            context.restore()

        # Draw the main image
        if input_path:
            context.save()

            try:
                input_surface = cairo.ImageSurface.create_from_png(input_path)
            except OSError:
                logging.exception('Image error on {}'.format(input_path))
            else:
                context.translate(SCREENSHOT_X, SCREENSHOT_Y)
                context.scale(SCREENSHOT_SCALE, SCREENSHOT_SCALE)
                context.set_source_surface(input_surface, 0, 0)
                context.get_source().set_filter(cairo.FILTER_NEAREST)
                context.paint()
            finally:
                context.restore()
        else:
            context.save()

            context.translate(SCREENSHOT_X, SCREENSHOT_Y)
            context.scale(SCREENSHOT_SCALE, SCREENSHOT_SCALE)
            self._draw_error_image(context)

            context.restore()

        context.pop_group_to_source()

        if render_index > total_render_frames - 1 - FPS:
            # Fade out ending
            context.paint_with_alpha((total_render_frames - 1 - render_index) / FPS)
        else:
            context.paint()

        surface.flush()
        surface.write_to_png(output_filename)

        logging.info(output_filename)

    def _draw_error_image(self, context):
        # Draw a grey rectangle with an X shape on it
        context.rectangle(0, 0, GAMEBOY_WIDTH, GAMEBOY_HEIGHT)
        context.set_source_rgb(0.5, 0.5, 0.5)
        context.fill()

        context.move_to(0, 0)
        context.line_to(GAMEBOY_WIDTH, GAMEBOY_HEIGHT)
        context.move_to(GAMEBOY_WIDTH, 0.0)
        context.line_to(0.0, GAMEBOY_HEIGHT)
        context.set_source_rgb(1.0, 1.0, 1.0)
        context.set_line_width(2)
        context.stroke()


if __name__ == '__main__':
    main()
