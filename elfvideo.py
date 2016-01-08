'''Script to generate TwitchPlaysPokemon Viet Crystal compilation video'''
# Copyright 2016 By Christopher Foo. License: MIT.

import argparse
import datetime
import logging
import multiprocessing
import os
import concurrent.futures
from itertools import zip_longest

import cairo
import itertools


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


FPS = 12


def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('input_dir')
    arg_parser.add_argument('output_dir')
    arg_parser.add_argument('--skip-exists', action='store_true')

    args = arg_parser.parse_args()

    input_filenames = tuple(sorted(
        os.path.basename(path) for path in os.listdir(args.input_dir)
    ))
    input_items = tuple(enumerate(input_filenames))
    input_items = tuple(itertools.chain(
        itertools.repeat(input_items[0], FPS),
        input_items,
        itertools.repeat(input_items[-1], FPS * 5),
    ))

    skip_exists = args.skip_exists

    with concurrent.futures.ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        for batch in grouper(enumerate(input_items), 100):
            futures = []
            for item in batch:
                if not item:
                    continue
                render_index, (index, filename) = item
                output_filename = os.path.join(args.output_dir, '{:05}.png'.format(render_index))

                if skip_exists and os.path.exists(output_filename):
                    continue

                futures.append(executor.submit(gen_frame, render_index, index, input_filenames, output_filename, args.input_dir, input_items))

            for future in concurrent.futures.as_completed(futures):
                future.result()

FONT_NAME = 'Nimbus Sans L'
FONT_NAME_SYMBOL = 'Symbola'

WIDTH = 1920
HEIGHT = 1080

CROSSFADE_RANGE = (-24, 4)

GAMEBOY_WIDTH = 480
GAMEBOY_HEIGHT = 432

SCREENSHOT_PADDING = 30
SCREENSHOT_SCALE = (HEIGHT - SCREENSHOT_PADDING * 2) / GAMEBOY_HEIGHT

SIDE_BAR_LEFT = SCREENSHOT_PADDING + GAMEBOY_WIDTH * SCREENSHOT_SCALE + SCREENSHOT_PADDING
SIDEBAR_SCREENSHOT_SCALE = (WIDTH - SCREENSHOT_PADDING - SIDE_BAR_LEFT) / GAMEBOY_WIDTH
SIDEBAR_SCREENSHOT_X = SIDE_BAR_LEFT
SIDEBAR_SCREENSHOT_Y = HEIGHT - SCREENSHOT_PADDING - GAMEBOY_HEIGHT * SIDEBAR_SCREENSHOT_SCALE

TITLE_TEXT_SIZE = 55
TITLE_Y = SCREENSHOT_PADDING + TITLE_TEXT_SIZE

DATE_TEXT_SIZE = 50
DATE_Y = TITLE_Y + SCREENSHOT_PADDING * 2 + DATE_TEXT_SIZE

DURATION_TEXT_SIZE = 50
DURATION_Y = DATE_Y + SCREENSHOT_PADDING + DURATION_TEXT_SIZE

FRAME_TEXT_SIZE = 50
FRAME_TEXT_Y = DURATION_Y + SCREENSHOT_PADDING + FRAME_TEXT_SIZE

NAME_TEXT_SIZE = 50
NAME_TEXT_Y = FRAME_TEXT_Y
NAME_TEXT_X = SIDE_BAR_LEFT + 250

ELF_ICON_WIDTH = 56
ELF_ICON_HEIGHT = 56
ELF_ICON_SCALE = FRAME_TEXT_SIZE / ELF_ICON_HEIGHT

TRAINER_ICON_WIDTH = 56
TRAINER_ICON_HEIGHT = 56
TRAINER_ICON_SCALE = FRAME_TEXT_SIZE / TRAINER_ICON_HEIGHT

BABA_NAME_INDEX = 48
BEST_NAME_INDEX = 210


def gen_frame(render_index, index, input_filenames, output_filename, input_dir, input_items):
    filename = input_filenames[index]
    input_path = os.path.join(input_dir, filename)

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
    context.move_to(SIDE_BAR_LEFT, TITLE_Y)
    context.show_text('Twitch Plays Viet Crystal')
    context.restore()

    # Draw timestamp
    context.save()
    context.set_source_rgb(1.0, 1.0, 1.0)
    context.set_font_size(DATE_TEXT_SIZE)
    context.move_to(SIDE_BAR_LEFT, DATE_Y)
    date_obj = datetime.datetime.fromtimestamp(
        int(os.path.splitext(input_filenames[index])[0])
    )
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
    first_date_obj = datetime.datetime.fromtimestamp(
        int(os.path.splitext(input_filenames[0])[0])
    )
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
    context.show_text(' {:05}'.format(index + 1))
    context.restore()

    # Start trainer infos
    context.save()

    context.push_group()

    # Draw trainer icon
    icon_surface = cairo.ImageSurface.create_from_png('Spr_C_Kris.png')
    context.save()
    context.translate(NAME_TEXT_X, NAME_TEXT_Y - NAME_TEXT_SIZE)
    context.scale(TRAINER_ICON_SCALE, TRAINER_ICON_SCALE)
    context.set_source_surface(icon_surface, 0, 0)
    context.get_source().set_filter(cairo.FILTER_BEST)
    context.paint()
    context.restore()

    # Draw trainer name
    context.set_source_rgb(1.0, 1.0, 1.0)
    context.set_font_size(NAME_TEXT_SIZE)
    context.move_to(NAME_TEXT_X + TRAINER_ICON_WIDTH * TRAINER_ICON_SCALE, NAME_TEXT_Y)
    context.select_font_face(FONT_NAME)
    context.show_text('BABA')

    context.pop_group_to_source()
    if index < BABA_NAME_INDEX:
        pass
    elif BABA_NAME_INDEX <= index <= BABA_NAME_INDEX + FPS:
        context.paint_with_alpha((index - BABA_NAME_INDEX) / FPS)
    else:
        context.paint()

    context.push_group()

    # Draw elf icon
    icon_surface = cairo.ImageSurface.create_from_png('157.png')
    context.save()
    context.translate(context.get_current_point()[0] + SCREENSHOT_PADDING, NAME_TEXT_Y - NAME_TEXT_SIZE)
    context.scale(ELF_ICON_SCALE, ELF_ICON_SCALE)
    context.set_source_surface(icon_surface, 0, 0)
    context.get_source().set_filter(cairo.FILTER_BEST)  # BORT
    context.paint()
    context.restore()

    # Draw elf name
    context.set_source_rgb(1.0, 1.0, 1.0)
    context.set_font_size(NAME_TEXT_SIZE)
    context.move_to(context.get_current_point()[0] + SCREENSHOT_PADDING + ELF_ICON_WIDTH * ELF_ICON_SCALE, NAME_TEXT_Y)
    context.select_font_face(FONT_NAME)
    context.show_text(' BEST')

    context.pop_group_to_source()

    if index < BEST_NAME_INDEX:
        pass
    elif BEST_NAME_INDEX <= index <= BEST_NAME_INDEX + FPS:
        context.paint_with_alpha((index - BEST_NAME_INDEX) / FPS)
    else:
        context.paint()

    context.restore()
    # End draw trainer infos

    # Draw the cross faded image
    for offset in range(CROSSFADE_RANGE[0], CROSSFADE_RANGE[1] + 1):
        sub_index = index + offset

        if sub_index < 0 or sub_index >= len(input_filenames):
            continue

        sub_path = os.path.join(input_dir, input_filenames[sub_index])
        try:
            sub_input_surface = cairo.ImageSurface.create_from_png(sub_path)
        except OSError:
            logging.exception('Image error on {}'.format(sub_path))
            continue

        context.save()
        context.translate(SIDEBAR_SCREENSHOT_X, SIDEBAR_SCREENSHOT_Y)
        context.scale(SIDEBAR_SCREENSHOT_SCALE, SIDEBAR_SCREENSHOT_SCALE)
        # context.translate(SCREENSHOT_PADDING, SCREENSHOT_PADDING)
        # context.scale(SCREENSHOT_SCALE, SCREENSHOT_SCALE)
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
        # context.translate(SIDEBAR_SCREENSHOT_X, SIDEBAR_SCREENSHOT_Y)
        # context.scale(SIDEBAR_SCREENSHOT_SCALE, SIDEBAR_SCREENSHOT_SCALE)
        context.translate(SCREENSHOT_PADDING, SCREENSHOT_PADDING)
        context.scale(SCREENSHOT_SCALE, SCREENSHOT_SCALE)
        context.set_source_surface(input_surface, 0, 0)
        context.get_source().set_filter(cairo.FILTER_NEAREST)
        context.paint()
    finally:
        context.restore()

    context.pop_group_to_source()

    if render_index > len(input_items) - 1 - FPS:
        # Fade out ending
        context.paint_with_alpha((len(input_items) - 1 - render_index) / FPS)
    else:
        context.paint()

    surface.flush()
    surface.write_to_png(output_filename)

    print(output_filename)


if __name__ == '__main__':
    main()
