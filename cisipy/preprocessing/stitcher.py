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
    """

    # Formatting arguments correctly for ImageJ macro code
    output_directory = str(output_directory)
    input_directory = f'{input_directory}/'

    args = imagej_instance.py.to_java({
      'basePath': input_directory,
      'filename': input_filename,
      'fusePath': output_directory
    })

    print("About to call imagej!")

    #result = imagej_instance.py.run_macro(STITCHING_MACRO, args)
    stitching_job = imagej_instance.script().run("macro.ijm", STITCHING_MACRO, True, args)

    return stitching_job

def stitch_all_samples(config, parallelize=0):
    """
    """
    # TODO: Fill in docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(workspace_directory, "sliced")
    output_directory = Path(workspace_directory, "stitched")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]
    path_to_fiji = config["path_to_fiji"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    
    imagej_instance = imagej.init(path_to_fiji)

    if parallelize > 1:
        num_processes = mp.cpu_count()
        print(num_processes)
        # child_pids = []
        processes = []
        for sample in samples:
        #    # TODO: This forking is necessary because of how ImageJ works. Consider posting to image.sc to find a fix.
        #    pid = os.fork()

        #    if pid:
        #        child_pids.append(pid)
        #    else:
        #        stitch_single_sample(sample, input_directory, output_directory, imagej_instance, parallelize - 1)
        #        break
     
        #for child_pid in child_pids:
        #    os.waitpid(child_pid, 0)
        #        
            process = mp.Process(target=stitch_single_sample, args=(sample, input_directory, output_directory, imagej_instance, parallelize - 1))
            process.start()
            processes.append(process)
    
        for process in processes:
            process.join()
    else:
        #imagej_instance = imagej.init(path_to_fiji)
        for sample in samples:
            stitch_single_sample(sample, input_directory, output_directory, imagej_instance, parallelize)

    # for sample in samples:
    #     stitch_single_sample(sample, input_directory, output_directory, imagej_instance)

def stitch_single_sample(sample, input_directory, output_directory, imagej_instance, parallelize=0):
    rounds = sample["rounds"]
    sample_name = sample["name"]

    sample_input_directory = input_directory / sample_name
    sample_output_directory = output_directory / sample_name
    sample_output_directory.mkdir(exist_ok=True)

    #child_pids = []
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
            # pid = os.fork()

            # if pid:
            #     child_pids.append(pid)
            # else:
            #     imagej_instance = imagej.init("Fiji.app")
            #     stitch(sample_input_directory, input_filename, output_directory, imagej_instance)
            #     break
            # process = mp.Process(target=stitch, args=(sample_input_directory, input_filename, output_directory, imagej_instance))
            # process.start()
            # processes.append(process)

        else:
            #imagej_instance = imagej.init("Fiji.app")
            #print(job)
            job.get()

    for job in jobs:
        #print(job)
        job.get()

    #for child_pid in child_pids:
    #    os.waitpid(child_pid, 0)
    #for process in processes:
    #    process.join()
