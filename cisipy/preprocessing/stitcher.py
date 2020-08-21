import scyjava_config
scyjava_config.add_options('-Xmx8g')

import imagej
import multiprocessing as mp
import os
from pathlib import Path

from importlib.resources import open_text

if __package__:
    with open_text(__package__, "Fuse.ijm") as macro:
        STITCHING_MACRO = macro.read()
else:
    with open("Fuse.ijm") as macro:
        STITCHING_MACRO = macro.read() 

def stitch(input_directory, input_filename, output_directory, imagej_instance):
    """
    Use the BigStitcher plugin to stitch together the series at input_filepath.

    See Fuse.ijm for the ImageJ macro code.

    Args:
      input_directory (Union[str, pathlib.Path]):
        Directory in which input microscopy file is located.
      input_filename (str):
        Name of microscopy file (excluding file extension).
      output_directory (Union[str, pathlib.Path]):
        Directory in which to output stitched images,
      imagej_instance (imagej.ImageJ):
        An ImageJ instance.

    Returns:
      A handle on the Java process that is completing the stitching job. This is useful
      for keeping track of concurrent stitching jobs.
        
    """

    # Formatting arguments correctly for ImageJ macro code
    output_directory = str(output_directory)
    input_directory = f'{input_directory}/'

    args = imagej_instance.py.to_java({
      'basePath': input_directory,
      'filename': input_filename,
      'fusePath': output_directory
    })

    stitching_job = imagej_instance.script().run("macro.ijm", STITCHING_MACRO, True, args)

    return stitching_job

def stitch_all_samples(config, parallelize=0):
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

    if parallelize > 1:
        num_processes = mp.cpu_count()
        processes = []
        for sample in samples:
            process = mp.Process(target=stitch_single_sample, args=(sample, input_directory, output_directory, imagej_instance, parallelize - 1))
            process.start()
            processes.append(process)
    
        for process in processes:
            process.join()
    else:
        for sample in samples:
            stitch_single_sample(sample, input_directory, output_directory, imagej_instance, parallelize)

def stitch_single_sample(sample, input_directory, output_directory, imagej_instance, parallelize=0):
    rounds = sample["rounds"]
    sample_name = sample["name"]

    sample_input_directory = input_directory / sample_name
    sample_output_directory = output_directory / sample_name
    sample_output_directory.mkdir(exist_ok=True)

    jobs = []
    for round_index, imaging_round in enumerate(rounds, start=1):
        round_directory = ("round%d" % round_index)
        filename = imaging_round["filename"]

        input_filename = (filename)
        output_directory = sample_output_directory / round_directory
        output_directory.mkdir(exist_ok=True)
        
        job = stitch(sample_input_directory, input_filename, output_directory, imagej_instance)
        if parallelize > 0:
            jobs.append(job)
        else:
            job.get()

    for job in jobs:
        job.get()
