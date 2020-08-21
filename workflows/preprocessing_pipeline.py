import toml
from cisipy.preprocessing import stitcher, spotfinder, register, segmenter
import argparse

parser = argparse.ArgumentParser(description='Parse arguments for preprocessing pipeline.')
parser.add_argument('config', type=str, help='Path to TOML config file.')
parser.add_argument('parallelize', type=int, help='Parallelization level.')

args = parser.parse_args()

if __name__ == "__main__":
    config = toml.load(args.config)
    stitcher.stitch_all_samples(config, parallelize=args.parallelize)
    spotfinder.find_spots_all_samples(config, parallelize=args.parallelize)
    register.register_all_samples(config, parallelize=args.parallelize)
    segmenter.segment_all_samples(config, parallelize=args.parallelize)
