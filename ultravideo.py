"""Script to generate TwitchPlaysPokemon Ultra timelapse compilation video"""
# Copyright 2017 By Christopher Foo. License: MIT.

import argparse
import datetime
import hashlib
import logging
import multiprocessing
import os
import concurrent.futures
import re
import tempfile
from itertools import zip_longest

import cairo
import itertools

import subprocess


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


ARCHIVE_SHA1_HASH = 'bf64b505272a376cf2eb90c915e39836e3a18dee'
FPS = 12


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('input_archive')
    arg_parser.add_argument('output_dir')
    arg_parser.add_argument('--skip-exists', action='store_true')

    args = arg_parser.parse_args()

    check_archive(args.input_archive)
    renderer = Renderer(args.input_archive, args.output_dir, skip_exists=args.skip_exists)

    renderer.run()


def check_archive(filename):
    hasher = hashlib.sha1()
    with open(filename, 'rb') as file:
        while True:
            data = file.read(4096)
            if not data:
                break
            hasher.update(data)

    if hasher.hexdigest().lower() != ARCHIVE_SHA1_HASH.lower():
        raise Exception('Archive file hash does not match the one Felkcraft has released.')


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


class Renderer:
    def __init__(self, archive_filename, output_dir, skip_exists=False):
        self.archive_filename = archive_filename
        self.output_dir = output_dir
        self.skip_exists = skip_exists

        self.temp_dir = tempfile.TemporaryDirectory()
        self.frame_infos = {}
        self.total_render_frames = None

    def run(self):
        self.unpack_files()

        input_indexes = tuple(sorted(self.frame_infos.keys()))
        input_indexes = tuple(itertools.chain(
            itertools.repeat(input_indexes[0], FPS),
            input_indexes,
            itertools.repeat(input_indexes[-1], FPS * 5),
        ))
        self.total_render_frames = len(input_indexes)

        with concurrent.futures.ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            for batch in grouper(enumerate(input_indexes), 100):
                futures = []
                for item in batch:
                    if not item:
                        continue
                    render_index, input_index = item
                    output_filename = os.path.join(self.output_dir, '{:05}.png'.format(render_index))

                    if self.skip_exists and os.path.exists(output_filename):
                        continue

                    futures.append(executor.submit(self.gen_frame, render_index, input_index, output_filename))

                for future in concurrent.futures.as_completed(futures):
                    future.result()

    def unpack_files(self):
        print('Reading archive')
        # Important: Force 7zip to display in UTC using environment variable
        output = subprocess.check_output(['7z', 'l', self.archive_filename, '-slt', '-ba'], env={'TZ': ''})
        infos = []

        info = {}

        for line in output.splitlines(keepends=False):
            line = line.decode()
            if line.startswith('Path = '):
                info['path'] = line[7:]
            elif line.startswith('Modified = '):
                info['modified'] = datetime.datetime.strptime(line[11:], '%Y-%m-%d %H:%M:%S')
            elif not line:
                assert 'path' in info, info
                assert 'modified' in info, info

                if info['path'].endswith('.png'):
                    infos.append(info)

                info = {}

        print('Extracting')

        subprocess.check_call(['7z', 'e', self.archive_filename, '-o{}'.format(self.temp_dir.name)])

        print('Renaming')

        infos = tuple(sorted(
            infos,
            key=lambda x: int(re.match(r'ultra/ultra-(\d+)\.png', x['path']).group(1))
        ))

        for index, info in enumerate(infos):
            filename = os.path.basename(info['path'])

            os.rename(
                os.path.join(self.temp_dir.name, filename),
                os.path.join(self.temp_dir.name, '{}.png'.format(index))
            )

            self.frame_infos[index] = info

    def gen_frame(self, render_index, input_index, output_filename):
        num_input_frames = len(self.frame_infos)
        input_dir = self.temp_dir.name
        input_path = os.path.join(input_dir, '{}.png'.format(input_index))

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
        title_x = (WIDTH - SCREENSHOT_PADDING * 2) / 2 - context.get_scaled_font().text_extents('Twitch Plays Pokémon Ultra')[2] / 2
        context.move_to(title_x, TITLE_Y)
        context.show_text('Twitch Plays Pokémon Ultra')
        context.restore()

        # Draw timestamp
        context.save()
        context.set_source_rgb(1.0, 1.0, 1.0)
        context.set_font_size(DATE_TEXT_SIZE)
        context.move_to(SIDE_BAR_LEFT, DATE_Y)
        date_obj = self.frame_infos[input_index]['modified']
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
        first_date_obj = self.frame_infos[0]['modified']
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
        context.restore()

        # Draw the cross faded image
        for offset in range(CROSSFADE_RANGE[0], CROSSFADE_RANGE[1] + 1):
            sub_index = input_index + offset

            if sub_index < 0 or sub_index >= num_input_frames:
                continue

            sub_path = os.path.join(input_dir, '{}.png'.format(sub_index))
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

        context.pop_group_to_source()

        if render_index > self.total_render_frames - 1 - FPS:
            # Fade out ending
            context.paint_with_alpha((self.total_render_frames - 1 - render_index) / FPS)
        else:
            context.paint()

        surface.flush()
        surface.write_to_png(output_filename)

        print(output_filename)


if __name__ == '__main__':
    main()
