from nd2reader import ND2Reader
import bioformats
import javabridge
import tifffile
import numpy as np
from pathlib import Path

import multiprocessing as mp

def get_editable_omexml(path):
    """
    Parse OMEXML header data from a Bio-Formats-compatible file.

    Used to parse metadata from .nd2 file and pass on to .ome.tiff file.
    """
   
    o = bioformats.get_omexml_metadata(path)
    new_omexml = bioformats.OMEXML(o)

    return new_omexml

def convert_nd2_to_ome_tiff(path, outpath):
    """
    Convert an nd2 file to an .ome.tif by saving each tile under a separate series.

    Uses the BigTIFF format to write the new .ome.tiff file.
    """

    path_to_nd2 = str(path)

    omexml = get_editable_omexml(path_to_nd2)
    limit = omexml.image_count
    
    xml_dict = tifffile.xml2dict(omexml.to_xml())
    with ND2Reader(path_to_nd2) as images:
        print(images.sizes)
        images.iter_axes = 'v'
        images.bundle_axes = "zcyx"
        with tifffile.TiffWriter(outpath, bigtiff=True) as tif:
            for series, tile in enumerate(images):
                # TODO: seems like, for some weird reason, the tiles are rotated incorrectly? Why?
                # Maybe it has to do with the order of the bundle axes

                rotated_tile = np.rot90(tile, k=1, axes=(2, 3))
                series_metadata = xml_dict["OME"]["Image"][series]
                tif.save(rotated_tile.astype(np.uint16), contiguous=False, metadata=series_metadata)

def slice_ome_tiff(input_filepath, output_filepath, start, end, use_bigtiff=False):
    """
    Build a new .ome.tiff with only the series that fall in the range start:end included (+ metadata).
    """
    # TODO: Add an IndexError or whatever later

    input_ome_tiff = tifffile.TiffFile(input_filepath)

    xml = input_ome_tiff.ome_metadata
    xml_dict = tifffile.xml2dict(xml)

    print(input_filepath)
    with tifffile.TiffWriter(output_filepath, bigtiff=use_bigtiff) as tif:
        for index in range(start, end):
            print(index)
            tile = input_ome_tiff.series[index].asarray()
            tile_metadata = xml_dict["OME"]["Image"][index]
            tif.save(tile.astype(np.uint16), contiguous=False, metadata=tile_metadata)

def convert_nd2_all_samples(config, parallelize=0):
    """
    """
    # TODO: Fill in docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(config["data_directory"])
    output_directory = Path(workspace_directory, "unstitched")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    # TODO: Figure out better error handling here (e.g. catch error and
    # kill JVM if error occurs)

    javabridge.start_vm(class_path=bioformats.JARS)
   
    processes = [] 
    for sample in samples:
        if parallelize > 0:
            process = mp.Process(target=convert_nd2_single_sample, args=(sample, input_directory, output_directory, parallelize - 1))
            process.start() 
            processes.append(process)
 
        else:
            convert_nd2_single_sample(sample, input_directory, output_directory)

    for process in processes:
        process.join()

    javabridge.kill_vm()

def convert_nd2_single_sample(sample, input_directory, output_directory, parallelize=0):
    """
    """

    rounds = sample["rounds"]
    sample_name = sample["name"]

    sample_output_directory = output_directory / sample_name
    sample_output_directory.mkdir(exist_ok=True)

    processes = []
    for round_index, imaging_round in enumerate(rounds):
        filename = imaging_round["filename"]

        input_filepath = (input_directory / filename).with_suffix(".nd2")
        output_filepath = (sample_output_directory / filename).with_suffix(".ome.tif")

        if parallelize > 0:
            process = mp.Process(target=convert_nd2_to_ome_tiff, args=(input_filepath, output_filepath))
            process.start() 
            processes.append(process)
        else:
            convert_nd2_to_ome_tiff(input_filepath, output_filepath)

    for process in processes:
        process.join()

def slice_ome_tiff_all_samples(config, start, end):
    """
    """
    # TODO: Fill in docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(workspace_directory, "unstitched")
    output_directory = Path(workspace_directory, "sliced")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    
    for sample in samples:
        slice_ome_tiff_single_sample(sample, input_directory, output_directory, start, end)

def slice_ome_tiff_single_sample(sample, input_directory, output_directory, start, end):
    rounds = sample["rounds"]
    sample_name = sample["name"]

    sample_input_directory = input_directory / sample_name
    sample_output_directory = output_directory / sample_name
    sample_output_directory.mkdir(exist_ok=True)

    for round_index, imaging_round in enumerate(rounds):
        filename = imaging_round["filename"]

        input_filepath = (sample_input_directory / filename).with_suffix(".ome.tif")
        output_filepath = (sample_output_directory / filename).with_suffix(".ome.tif")

        slice_ome_tiff(input_filepath, output_filepath, start, end, use_bigtiff=True)
