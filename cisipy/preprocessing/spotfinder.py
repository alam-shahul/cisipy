import numpy as np
import imageio
from pathlib import Path
import multiprocessing as mp

from starfish import data, FieldOfView
from starfish.types import Axes, Features
from starfish.image import Filter
from starfish.core.imagestack.imagestack import ImageStack
from starfish.spots import DecodeSpots, FindSpots
from starfish import Codebook

def find_spots_all_samples(config, parallelize=0):
    """
    """
    # TODO: Fill in docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(workspace_directory, "stitched")
    output_directory = Path(workspace_directory, "spots_only")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    if parallelize > 0:
        num_processes = mp.cpu_count()
        print(num_processes)
        processes = []
        for sample in samples:
            process = mp.Process(target=find_spots_single_sample, args=(sample, input_directory, output_directory, parallelize - 1))
            process.start()
            processes.append(process)

        for process in processes:
            process.join()
    else:
        for sample in samples:
            find_spots_single_sample(sample, input_directory, output_directory)

def find_spots_single_sample(sample, input_directory, output_directory, parallelize=0):
    """
    """
    # TODO: Fill in docstring

    sample_name = sample["name"]
    rounds = sample["rounds"]

    processes = []
    for round_index, imaging_round in enumerate(rounds, start=1):
        if parallelize > 0:
            process = mp.Process(target=find_spots_in_round, args=(sample_name, round_index, imaging_round, input_directory, output_directory))
            process.start()
            processes.append(process)
        else:
            find_spots_in_round(sample_name, round_index, imaging_round, input_directory, output_directory)

    for process in processes:
        process.join()

def find_spots_in_round(sample_name, round_index, imaging_round, input_directory, output_directory):
    """
    """

    round_directory = ("round%d" % round_index)
    sample_input_subdirectory = input_directory / sample_name / round_directory
    sample_output_subdirectory = output_directory / sample_name / round_directory
    sample_output_subdirectory.mkdir(parents=True, exist_ok=True)

    channels = imaging_round["channels"]
    filename = imaging_round["filename"]
    reference_channel = imaging_round["reference_channel"] 
    for channel_index, channel in enumerate(channels):
        input_filename = filename + ("_fused_tp_0_ch_%d.tif" % channel_index)
        output_filename = channel + ".tif"
        input_path = sample_input_subdirectory / input_filename
        output_path = sample_output_subdirectory / output_filename

        if channel_index == reference_channel:
            image_stack = imageio.volread(input_path)
            max_filtered_image_stack = image_stack.max(0)
            imageio.imsave(output_path, max_filtered_image_stack)
        else:
            find_spots(input_path, output_path)


def find_spots(input_path, output_path, intensity_percentile=99.995, filter_width=2, small_peak_min=4, small_peak_max=100,
               big_peak_min=25, big_peak_max=10000, small_peak_dist=2, big_peak_dist=0.75, block_dim_fraction=0.25,
               spot_pad_pixels=2, keep_existing=False):
    """
    Find and keep only spots from stitched images.

    """

    image_stack = imageio.volread(input_path)

    print(image_stack.shape)
    thresholded_image = np.copy(image_stack)
    
    _, height, width = image_stack.shape

    threshold = np.percentile(thresholded_image, intensity_percentile)
    thresholded_image[thresholded_image > threshold] = threshold + (np.log(thresholded_image[thresholded_image > threshold] - threshold)/np.log(1.1)).astype(thresholded_image.dtype)

    #May need to fiddle with the sigma parameters in each step, depending on the image.
    
    #High Pass Filter (Background Subtraction)
    gaussian_high_pass = Filter.GaussianHighPass(sigma=(1, filter_width, filter_width), is_volume=True)
    
    # enhance brightness of spots
    laplace_filter = Filter.Laplace(sigma=(0.2, 0.5, 0.5), is_volume=True)
    local_max_peakfinder_small = FindSpots.LocalMaxPeakFinder(
        min_distance=small_peak_dist,
        stringency=0,
        min_obj_area=small_peak_min,
        max_obj_area=small_peak_max,
        min_num_spots_detected=2500,
        is_volume=True,
        verbose=True
    )

    local_max_peakfinder_big = FindSpots.LocalMaxPeakFinder(
        min_distance=big_peak_dist,
        stringency=0,
        min_obj_area=big_peak_min,
        max_obj_area=big_peak_max,
        min_num_spots_detected=2500,
        is_volume=True,
        verbose=True
    )

    synthetic_codebook= Codebook.synthetic_one_hot_codebook(n_round=1, n_channel=1, n_codes=1)
    decoder = DecodeSpots.PerRoundMaxChannel(codebook=synthetic_codebook)

    block_dimension = int(max(thresholded_image.shape) * block_dim_fraction)
    spot_coordinates= np.zeros((0, 2), dtype=np.int64)

    # Finding spots by block_dimension x block_dimension size blocks
    # We skip the blocks at the edges with the - 1 (TODO: pad to full block size)
    for row in range(0, height - 1, block_dimension):
        for column in range(0, width - 1, block_dimension):
            # Cutout block and expand dimensions for channel and round
            block = thresholded_image[np.newaxis, np.newaxis, :, row:row+block_dimension, column:column+block_dimension]
            images = ImageStack.from_numpy(block)
            high_pass_filtered = gaussian_high_pass.run(images, verbose=False, in_place=False)
            laplace = laplace_filter.run(high_pass_filtered, in_place=False,verbose=False)

            small_spots = local_max_peakfinder_small.run(laplace.reduce({Axes.ZPLANE}, func="max"))
            decoded_intensities = decoder.run(spots=small_spots)
            small_spot_coords = np.stack([decoded_intensities[Axes.Y.value], decoded_intensities[Axes.X.value]]).T
            
            big_spots = local_max_peakfinder_big.run(laplace.reduce({Axes.ZPLANE}, func="max"))
            decoded_intensities = decoder.run(spots=big_spots)
            big_spot_coords = np.stack([decoded_intensities[Axes.Y.value], decoded_intensities[Axes.X.value]]).T
            
            all_spot_coords = np.vstack([small_spot_coords, big_spot_coords])
            all_spot_coords += (row, column)

            spot_coordinates = np.vstack([spot_coordinates, all_spot_coords])

    # Copying over only non-zero pixels
    image_spots = np.zeros((height, width), dtype=np.uint16)
    for spot_coordinate in spot_coordinates:
        spot_column, spot_row = spot_coordinate
        for row in range(max(0, spot_column-spot_pad_pixels), min(spot_column+spot_pad_pixels+1, height)):
            for column in range(max(0, spot_row-spot_pad_pixels), min(spot_row+spot_pad_pixels+1, width)):
                # Max projecting over z-stack
                image_spots[row, column] = image_stack[:, row, column].max(0)

    imageio.imsave(output_path, image_spots)

    return image_spots
