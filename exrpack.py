#!/usr/bin/env python3
from pathlib import Path
import OpenEXR
from PIL import Image
import Imath
import numpy as np

def exr_to_packed_png(in_path, out_path):
    in_exr = OpenEXR.InputFile(in_path)
    dw = in_exr.header()['dataWindow']
    width, height = dw.max.x - dw.min.x + 1, dw.max.y - dw.min.y + 1
    r, g, b = [np.frombuffer(in_exr.channel(channel, Imath.PixelType(OpenEXR.FLOAT)), dtype=np.float32).reshape(height, width) for channel in ('R', 'G', 'B')]
    r_ = np.multiply(np.multiply(np.fmod(r, 1/16), 16), 255).astype(np.uint8)
    g_ = np.multiply(np.multiply(np.fmod(g, 1/16), 16), 255).astype(np.uint8)
    b_ = np.floor(np.multiply(r, 16)).astype(np.uint8) + np.multiply(np.floor(np.multiply(g,16)), 16).astype(np.uint8)  # TODO should probably convert to int earlier in this one
    a_ = np.multiply(np.subtract(1, b), 255).astype(np.uint8)
    packed = Image.fromarray(np.dstack((r_, g_, b_, a_)), mode='RGBA')
    packed.save(out_path)
    # packed = Image.new('RGBA', (width, height))
    # R, G, B = [np.frombuffer(in_exr.channel(channel, Imath.PixelType(OpenEXR.FLOAT)), dtype=np.float32).reshape(height, width) for channel in ('R', 'G', 'B')]
    # for x in range(width):
    #     for y in range(height):
    #         r, g, b = [C[y, x] for C in (R, G, B)]
    #         # packed.putpixel((x, y), (int(r*255), int(g*255), int(b*255)))
    #         packed.putpixel((x, y), (int((r%(1/16))*16*255), int((g%(1/16))*16*255), int(np.floor(r*16) + np.floor(g*16)*16), int((1-b)*255)))
    # packed.save(out_path)



if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path, nargs='?')

    args = parser.parse_args()

    if args.output is None:
        args.output = args.input.with_name(f'{args.input.stem}__packed.png')

    exr_to_packed_png(str(args.input.absolute()), str(args.output.absolute()))

