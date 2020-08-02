import scyjava_config
scyjava_config.add_options('-Xmx10g')

import imagej
from pathlib import Path

with open("Fuse.ijm") as macro:
    STITCHING_MACRO = macro.read()

def stitch(input_directory, input_filename, output_directory, imagej_instance):
    """
    Use the BigStitcher plugin to stitch together the series at input_filepath.

    See Fuse.ijm for the ImageJ macro code.
    """

    # Formatting arguments correctly for ImageJ macro code
    output_directory = str(output_directory)
    input_directory = f'{input_directory}/'

    args = {
      'basePath': input_directory,
      'filename': input_filename,
      'fusePath': output_directory
    }

    result = imagej_instance.py.run_macro(STITCHING_MACRO, args)

    return result

def stitch_all_samples(config):
    """
    """
    # TODO: Fill in docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(workspace_directory, "unstitched")
    output_directory = Path(workspace_directory, "stitched")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]
    path_to_fiji = config["path_to_fiji"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    
    imagej_instance = imagej.init(path_to_fiji)

    for sample in samples:
        stitch_single_sample(sample, input_directory, output_directory, imagej_instance)

def stitch_single_sample(sample, input_directory, output_directory, imagej_instance):
    rounds = sample["rounds"]
    sample_name = sample["name"]

    sample_input_directory = input_directory / sample_name
    sample_output_directory = output_directory / sample_name
    sample_output_directory.mkdir(exist_ok=True)

    for round_index, imaging_round in enumerate(rounds, start=1):
        round_directory = ("round%d" % round_index)
        filename = imaging_round["filename"]

        input_filename = (filename + "_fov_0_4")
        output_directory = sample_output_directory / round_directory
        output_directory.mkdir(exist_ok=True)

        stitch(sample_input_directory, input_filename, output_directory, imagej_instance)
