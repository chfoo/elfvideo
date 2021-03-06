# elfvideo
Script to generate TwitchPlaysPokemon Viet Crystal (and others) timelapse compilation video


## Usage

Requires:

* Python 3.4+
* [PIL](https://pillow.readthedocs.io)
* PyCairo

Run:

        python3 elfvideo.py ./input_dir/ ./output_dir/

This will output the video frames which you can encode into a video. ffmpeg can do this easily.

### PMD

PMD is a bit more complicated but most of the data is already included or available as a easy download.

Requires in addition:

* youtube-dl
* ffmpeg
* [tppocr](https://github.com/chfoo/tppocr)
* [arrow](https://arrow.readthedocs.io/en/latest/)

To do the whole thing from scratch, run:

1. `python3 pmdred/pull_api.py inputs.db`
2. `python3 pmdred/unpack.py tpp_pmdrrt_screenshots.7z images/`
3. `python3 twitch/get_vod_list.py json/`
4. `python3 twitch/json_to_db.py json/ vods.db`
5. `python3 pmdred/get_missing_frames.py images/ inputs.db vods.db`
6. `python3 pmdred/pmdvideo.py images/ output-frames/ inputs.db`

If you just want to generate the video frames, do the last step above.

Sample ffmpeg command: `ffmpeg -r 12 -i "images/%05d.png" -r 12 -c:v libvpx-vp9 -b:v 4000k -crf 33 -threads 8 -tile-columns 6 -pix_fmt yuv420p -f webm out.webm`


## Images

* Viet crystal: https://archive.org/details/tpp_elf_images
* Ultra romhack: https://drive.google.com/file/d/0BxXNZYVh03vRQ2R2QWZIUm5kaUU/view?usp=sharing or https://archive.org/details/tpp_ultra_screenshots
* Pokémon Mystery Dungeon: Red Rescue Team: https://archive.org/details/tpp_pmd_red_sidegame_screenshots

## Credits

Source code Copyright 2016-2017 By Christopher Foo. License: MIT.



