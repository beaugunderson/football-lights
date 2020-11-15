#!/usr/bin/env python3

from collections import defaultdict
from csv import DictReader
from time import sleep
from typing import Dict

import requests

from colour import Color
from phue import Bridge

HUE_BRIDGE_IP = '192.168.50.43'

NFL = {}


def hex_to_rgb(color_hex):
    color_hex = color_hex.lstrip('#')
    color_length = len(color_hex)

    return tuple(
        int(color_hex[i:i + color_length // 3], 16) / 255.0
        for i in range(0, color_length, color_length // 3))


def rgb_to_xy(red, green, blue):
    """ conversion of RGB colors to CIE1931 XY colors
    Formulas implemented from: https://gist.github.com/popcorn245/30afa0f98eea1c2fd34d
    Args:
        red (float): a number between 0.0 and 1.0 representing red in the RGB space
        green (float): a number between 0.0 and 1.0 representing green in the RGB space
        blue (float): a number between 0.0 and 1.0 representing blue in the RGB space
    Returns:
        xy (list): x and y
    """
    # gamma correction
    red = pow((red + 0.055) / (1.0 + 0.055), 2.4) if red > 0.04045 else (red / 12.92)
    green = pow((green + 0.055) / (1.0 + 0.055), 2.4) if green > 0.04045 else (green / 12.92)
    blue =  pow((blue + 0.055) / (1.0 + 0.055), 2.4) if blue > 0.04045 else (blue / 12.92)

    # convert rgb to xyz
    x = red * 0.649926 + green * 0.103455 + blue * 0.197109
    y = red * 0.234327 + green * 0.743075 + blue * 0.022598
    z = green * 0.053077 + blue * 1.035763

    # convert xyz to xy
    x = x / (x + y + z)
    y = y / (x + y + z)

    return [x, y]


with open('./nfl_data.csv') as nfl_data:
    reader = DictReader(nfl_data)

    for row in reader:
        colors = [
            row['primary'],
            row['secondary'],
            row['tertiary'],
            row['quaternary'],
        ]

        colors = [color for color in colors if color != '#000000']
        converted_colors = [Color(color) for color in colors[0:2]]

        for color in converted_colors:
            # color.luminance = 0.75
            color.saturation = 0.75

        final_colors = [(color.red, color.green, color.blue) for color in converted_colors]

        NFL[row['abbr']] = {
            'name': row['team'],
            'colors': final_colors,
            'xy': [rgb_to_xy(*color) for color in final_colors],
        }


# from pprint import pprint
# pprint(NFL)


def connect_bridge():
    bridge = Bridge(HUE_BRIDGE_IP)
    bridge.connect()

    return bridge


def lights_on_color(lights, color):
    for light in lights:
        if not light.on:
            continue

        light.brightness = 255
        light.xy = color


def lights_off(lights):
    for light in lights:
        light.brightness = 0


def handle_score(team, new_score):
    print(f'{NFL[team]["name"]} scored! New score: {new_score}')

    if team not in ('SEA', 'LA'):
        return

    print(f'Handling lights...')

    bridge = connect_bridge()

    on_lights = []

    try:
        for light in bridge.lights:
            if not light.on:
                continue

            on_lights.append(light)

        for i in range(5):
            color = NFL[team]['xy'][0 if i % 2 == 0 else 1]

            lights_on_color(on_lights, color)
            sleep(0.25)
    except ConnectionResetError as e:
        print(f'Failed: {e}')

    bridge.run_scene('Living Room', 'Seahawks')


def main():
    scores: Dict[str, int] = defaultdict(int)
    initialized = False

    while True:
        response = requests.get('http://static.nfl.com/liveupdate/scores/scores.json')

        score_json = response.json()

        for date, game in score_json.items():
            away = game['away']['abbr']
            home = game['home']['abbr']

            away_score = game['away']['score']['T'] or 0
            home_score = game['home']['score']['T'] or 0

            if initialized:
                if scores[away] != away_score:
                    handle_score(away, away_score)

                if scores[home] != home_score:
                    handle_score(home, home_score)

            scores[away] = away_score
            scores[home] = home_score

        if not initialized:
            initialized = True

        sleep(30)


if __name__ == '__main__':
    main()
