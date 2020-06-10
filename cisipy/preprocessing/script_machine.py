import json
from util import *
from parse_and_z_project import parse_and_z_project
from stitch_from_coords import stitch_from_coords
from imagej_stitching import imagej_stitching
from subtract_background import subtract_background
from apply_channel_thresholds import apply_channel_thresholds
from calculate_and_apply_flat_field_correction import calculate_and_apply_flat_field_correction
from register_and_tile_images import register_and_tile_images

"""
Steps taken during preprocessing:

0. run parse_and_z_project.py, which parses and max z-projects each nd2 file
1. use imagej_stitching.py to calculate stitching in DAPI channel for every tissue/round
2. use stitch_from_coords.py to stitch together images for each gene x round combination and apply median filter
3. run subtract_background
4. use Fiji to determine intensity thresholds for each channel based on previous stitched images (setting max to 150% of min)
5. run apply_channel_thresholds.py
6. run calculate_and_apply_flat_field_correction.py
7. run save_registered_images.py to register across rounds and break into tiles
8. run write_tf_records.py
"""

parser = argparse.ArgumentParser()
parser.add_argument('--parameter-filepath', help='Path to JSON file containing parameters necessary for scripts to run')
parser.add_argument('--start', help='Index of first script in pipeline to run', type=int)
parser.add_argument('--end', help='Index of last script in pipeline to run', type=int)
args, _ = parser.parse_known_args()

filepath = args.parameter_filepath
with open(filepath) as f:
    parameters = json.load(f)

parameter_specification = [
    ["background_path_regex", "source_path_regex", "fov_order_map_path", "context_to_channel_map_path", "outpath"],
    ["tissue_directory_regex", "cols", "rows"],
    ["tissue_directory_regex", "height", "width", "ordered_channels"],
    ["tissue_directory_regex", "ordered_channels", "background_scaling_factors", "blank_round_number"],
    ["tissue_directory_regex", "ordered_channels", "channel_threshold_filepath", "blank_round_number"],
    ["tissue_directory_regex", "blank_round_number", "height", "width", "filter_width"],
    ["tissue_directory_regex", "tile_size", "blank_round_number"]
]

function_specification = [
    parse_and_z_project,
    imagej_stitching,
    stitch_from_coords,
    subtract_background,
    apply_channel_thresholds,
    calculate_and_apply_flat_field_correction,
    register_and_tile_images
]

if args.start > args.end:
    raise ValueError("Last index must be larger than first index.")

for index in range(args.start, args.end + 1):
    if index > len(parameter_specification):
        raise ValueError("Not a valid script_index.")
        
    necessary_parameters = parameter_specification[index]
    missing_parameters = [key for key in necessary_parameters if key not in parameters]
    if missing_parameters:
        raise ValueError("The input JSON file is missing the following necessary parameters: {}".format(missing_parameters))
    
    script_function = function_specification[index]
    print("Starting script %d" % index)
    script_function(*[parameters[key] for key in necessary_parameters])
    print("Finished script %d!" % index)
