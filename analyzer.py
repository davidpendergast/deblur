import deblur
import sys
import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A tool for analyzing and de-blurring images.')
    parser.add_argument('-f', type=str, metavar="filepath", default="data/3x3_circle_in_10x10.png", help="the image to analyze.")
    parser.add_argument('-r', type=str, metavar="pixels", default=12, help=f'the radius to check.')
    parser.add_argument('-i', type=int, metavar="int", default=100, help=f'the number of iterations.')
    parser.add_argument('--blur', type=float, metavar="float", default="box", help=f'the (assumed) style of blur.')

    args = parser.parse_args()

    filename = args.f
    radius_range = (args.rlow, args.rhigh)
    blur_style = args.par