from nd2reader import ND2Reader
import bioformats
import javabridge
import tifffile
import numpy as np
from pathlib import Path

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
        images.iter_axes = 'v'
        images.bundle_axes = "zcyx"
        with tifffile.TiffWriter(outpath, bigtiff=True) as tif:
            for series, tile in enumerate(images):
                series_metadata = xml_dict["OME"]["Image"][series]
                tif.save(tile.astype(np.uint16), contiguous=False, metadata=series_metadata)

def slice_ome_tiff(input_filepath, output_filepath, start, end, use_bigtiff=False):
    """
    Build a new .ome.tiff with only the series that fall in the range start:end included (+ metadata).
    """
    # TODO: Add an IndexError or whatever later

    input_ome_tiff = tifffile.TiffFile(input_filepath)

    xml = input_ome_tiff.ome_metadata
    xml_dict = tifffile.xml2dict(xml)

    with tifffile.TiffWriter(output_filepath, bigtiff=use_bigtiff) as tif:
        for index in range(start, end):
            print(index)
            tile = input_ome_tiff.series[index].asarray()
            tile_metadata = xml_dict["OME"]["Image"][index]
            tif.save(tile.astype(np.uint16), contiguous=False, metadata=tile_metadata)

def convert_nd2_all_samples(config):
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
    
    for sample in samples:
        convert_nd2_single_sample(sample, input_directory, output_directory)

    javabridge.kill_vm()

def convert_nd2_single_sample(sample, input_directory, output_directory):
    """
    """

    rounds = sample["rounds"]
    sample_name = sample["name"]

    sample_output_directory = output_directory / sample_name
    sample_output_directory.mkdir(exist_ok=True)

    for round_index, imaging_round in enumerate(rounds):
        filename = imaging_round["filename"]

        input_filepath = (input_directory / filename).with_suffix(".nd2")
        output_filepath = (sample_output_directory / filename).with_suffix(".ome.tif")

        convert_nd2_to_ome_tiff(input_filepath, output_filepath)

def slice_ome_tiff_all_samples(config, start, end):
    """
    """
    # TODO: Fill in docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(workspace_directory, "unstitched")
    output_directory = Path(workspace_directory, "unstitched")

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
        output_filepath = (sample_output_directory / (filename + "_fov_%d_%d" % (start, end))).with_suffix(".ome.tif")

        slice_ome_tiff(input_filepath, output_filepath, start, end, use_bigtiff=True)
