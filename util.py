import numpy as np
import imageio
import glob, os
import re
import argparse
import pickle
import json
import pyfftw

from scipy import ndimage
from scipy.ndimage import median_filter
from scipy.ndimage import fourier_shift
from scipy.ndimage import gaussian_filter
from scipy.misc import imsave
from skimage.feature import register_translation
from skimage.transform import rescale
from pims import ND2_Reader
from collections import defaultdict
from ast import literal_eval

def adjust_contrast(image, c0=10, c1=0.3, eps=1e-5, ptile=99.5):
    """
    Use a sigmoid model to adjust contrast for an image.
    """
    contrast_adjusted_image = image/(np.percentile(image, ptile) + eps)
    contrast_adjusted_image = 1/(1 + np.exp(-(contrast_adjusted_image - c1)*c0))
    return contrast_adjusted_image

def _bytes_feature(value):
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

def _int64_feature(value):
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

def write_record_from_numpy(image, tissue, fov, tfrecords_filename, patch_height=512, patch_width=512):
    tissue_byte = tf.compat.as_bytes(tissue)
    fov_byte = tf.compat.as_bytes(fov)
    writer = tf.python_io.TFRecordWriter(tfrecords_filename + '.tfrecords')
    for i in range(0,image.shape[0],patch_height):
        for j in range(0,image.shape[1],patch_width):
            image_raw = image[i:i+patch_height,j:j+patch_width]
            h,w,c = image_raw.shape
            image_raw = image_raw.tostring()
            example = tf.train.Example(features=tf.train.Features(feature={'raw_data': _bytes_feature(image_raw), 'height': _int64_feature(h), 'width': _int64_feature(w), 'channels': _int64_feature(c), 'tissue': _bytes_feature(tissue_byte), 'fov': _bytes_feature(fov_byte), 'row_offset': _int64_feature(i), 'col_offset': _int64_feature(j)}))
            writer.write(example.SerializeToString())
    writer.close()

def shift_background(im, im_bg):
    n,m = im.shape
    diff_min = np.inf
    for i in range(-20, 20, 2):
        for j in range(-20, 20, 2):
            im_bg_adj = im_bg[100+i:n-100+i, 100+j:m-100+j]
            diff = np.linalg.norm(im[100:n-100, 100:m-100] - im_bg_adj)
            if diff < diff_min:
                best = (i,j)
                diff_min = diff
    i,j = best
    im_bg_adj = im_bg[max(0,i):min(n,n+i),max(0,j):min(m,m+j)]
    im_bg_adj = np.pad(im_bg_adj,((max(0,-i),max(0,i)),(max(0,-j),max(0,j))),'constant')
    return im_bg_adj

# New code - 1/7/19
def find_random_background(im, n=2500, radius=16):
	# find a region with low total variation
	total_variations = []
	sub_ims = []
	rows = np.random.randint(radius, im.shape[0] - radius, size=n)
	cols = np.random.randint(radius, im.shape[1] - radius, size=n)
	for row, col in zip(rows,cols):
		im_sub = im[row-radius:row+radius, col-radius:col+radius]
        # This line does all the magic
		total_variation = np.average(np.diff(im_sub,axis=0)**2) + np.average(np.diff(im_sub,axis=1)**2)
		total_vartiations.append(total_variation)
		sub_ims.append(im_sub)
	xs = np.argsort(total_variations)
	return np.average([sub_ims[i] for i in xs[:10]])

# Newer code - 1/16/19
def parse_coordinates_file(filepath):
    filename_to_coordinates = {}
    max_x = max_y = 0

    with open(filepath, 'r') as descriptor:
        # Discard first four lines and last line
        coordinate_information = descriptor.read().split('\n')[4:-1]

        for line in coordinate_information:
            data = line.strip().split(';')
            print(data)
            fov = data[0]
            coordinate_pair = np.clip(np.rint(literal_eval(data[2].strip())).astype(int), 0, None)
 
            filename_to_coordinates[fov] = coordinate_pair

            x_coord, y_coord = coordinate_pair
            max_x = max(max_x, x_coord)
            max_y = max(max_y, y_coord)           

    return filename_to_coordinates, max_x, max_y


def find_shift(first_image, second_image, scale = 1):
    """
    Obtain shift that aligns second_image to first_image, after rescaling both images to given resolution
    """
    rescaled_first_image = rescale(first_image, scale)
    rescaled_second_image = rescale(second_image, scale)
    shift, error, phase_difference = register_translation(rescaled_first_image, rescaled_second_image)
    return shift / scale

def apply_shift_to_images(images, shift):
    """
    Apply translation to image. Applies the shift to the Fourier transform of the images,
    and then inverse Fourier transforms the result.
    """
    offset_images = [fourier_shift(np.fft.fftn(image), shift) for image in images]
    offset_images = [np.fft.ifftn(image) for image in offset_images]
    offset_images = np.array(offset_images).astype(np.float32)
    return offset_images

def crop_shifted_images(images, shift):
    """
    Crop images according to x/y shifts. 
    """

    x_shift, y_shift = shift

    # Calculate the minimum and maximum horizontal shift
    if x_shift < 0:
        images = images[:, :x_shift]
    elif x_shift > 0:
        images = images[:, x_shift:]
    if y_shift < 0:
        images = images[:, :, :y_shift]
    elif y_shift > 0:
        images = images[:, :, y_shift:]
    return images

def parse_nd2_file(nd2_filepath):
    """
    Parse images and metadata necessary for stitching from nd2 file.
    """

    with ND2_Reader(nd2_filepath) as images:
        #print("The metadata is ", str(images.metadata).encode('utf-8'))
        
        num_fov = images.sizes['m']
        num_channels = images.sizes['c']
        num_rows = images.sizes['y']
        num_columns = images.sizes['x']

        fields_of_view = list(range(num_fov))
        channels = [images.metadata['plane_' + str(num)]['name'] for num in range(num_channels)]
        microns_per_pixel = images.metadata['calibration_um']

        try:
            images.iter_axes = 'mc'
            images.bundle_axes = 'zyx'
        except:
            images.iter_axes = 'c'
            images.bundle_axes = 'zyx'

        aggregated_images = []
        coordinate_pairs = []
        for z_stack in images:
            aggregated_image = np.max(z_stack, axis = 0)
            aggregated_images.append(aggregated_image)
            coordinate_pair = z_stack.metadata['y_um'], z_stack.metadata['x_um']
            coordinate_pairs.append(coordinate_pair)

    aggregated_images = np.reshape(aggregated_images,(num_fov, num_channels, num_rows, num_columns))
    coordinate_pairs = np.average(np.reshape(coordinate_pairs, (num_fov, num_channels, 2)), axis = 1)
    print("Coordinate pairs is \n" + str(coordinate_pairs))
    print("Shape is " + str(aggregated_images.shape))
    
    data = {
               "aggregated_images": aggregated_images,
               "coordinate_pairs": coordinate_pairs,
               "fields_of_view": fields_of_view,
               "channels": channels,
               "microns_per_pixel": microns_per_pixel 
           }

    return data

def calculate_flat_field(images):
    """
    Calculates an approximation of the flat field for the microscope by obtaining a per-pixel median and
    then applying a Gaussian filter. 
    """

    _, height, _ = images.shape
    print(images.shape)
    filter_sigma = height // 16
    flat_field = gaussian_filter(normalize_and_convert_to_16_bit(np.median(images, axis = 0)), filter_sigma)
   
    print(flat_field.shape)
    return flat_field 

def normalize_and_convert_to_16_bit(image):
    """
    Normalize an image and convert it to a 16-bitdepth scale; usually used right before saving an image.
    """
    
    MAX_INTENSITY = np.iinfo(np.uint16).max
    reduced_image = (image.astype(np.float64) - image.min())/(image.ptp())
    reduced_image = MAX_INTENSITY * reduced_image
    reduced_image = reduced_image.astype(np.uint16)

    return reduced_image

# New code - 1/10/19
def parse_rounds(filepath):
	round_tissue_combination_to_channel_map = defaultdict(list)
	f = open(filepath,encoding='utf-8')
	header = f.readline()
	for line in f:
		tissue, round_number, channel_label = line.strip().split(',')
		round_tissue_combination_to_channel_map[(tissue, round_number)].append(channel_label)
	f.close()
	return round_tissue_combination_to_channel_map

def apply_shifts(image, shift):
    offset_image = []
    for channel_index in range(image.shape[2]):
        print(image[:, :, channel_index].shape)
        print(image[:, :, channel_index].dtype)
        print("Calculating Fourier transform...")
        #transformed_slice = np.fft.fftn(image[:, :, channel_index])
        transformed_slice = pyfftw.interfaces.numpy_fft.fftn(image[:, :, channel_index])
        print("Shifting transformed image...")
        offset_im = fourier_shift(transformed_slice, shift)
        print(offset_im.shape)
        print(offset_im.dtype)
        offset_image.append(pyfftw.interfaces.numpy_fft.ifftn(offset_im))
        #offset_image.append(np.fft.ifftn(offset_im))
    offset_image = np.transpose(offset_image, axes = [1, 2, 0]).astype(np.float32)
    return offset_image

def find_all_shifts(ref_image, other_images):
    shifts = []
    for other_image in other_images:
        shift = find_shift(ref_image, other_image, scale=0.25)
        shifts.append(shift)
    return shifts

def crop_all_shifted(images, shifts):
    min_y_shift, min_x_shift = np.min(shifts,axis=0).astype(np.int)
    max_y_shift, max_x_shift = np.max(shifts,axis=0).astype(np.int)
    if min_y_shift < 0:
        images = images[:, :min_y_shift]
    if max_y_shift > 0:
        images = images[:, max_y_shift:]
    if min_x_shift < 0:
        images = images[:, :, :min_x_shift]
    if max_x_shift > 0:
        images = images[:, :, max_x_shift:]
    return images

def tilify(image, tile_size):
    rows, columns, _ = image.shape
    tiles = []
    tile_pattern = []
    tile_index = 0
    for row in range(0, rows, tile_size):
        tile_row = []
        for column in range(0, columns, tile_size):
            cutout = image[row:row+tile_size, column:column+tile_size]
            actual_height, actual_width, _ = cutout.shape
            tile = np.pad(cutout, [(0, tile_size - actual_height), (0, tile_size - actual_width), (0, 0)], 'constant')
            tiles.append(tile)
            tile_row.append(tile_index)
            tile_index += 1
        tile_pattern.append(tile_row)
    tiles = np.array(tiles)
    tile_pattern = np.array(tile_pattern)    

    return tiles, tile_pattern

def apply_threshold_and_rescale(channel_slice, lower_threshold, upper_threshold):
    datatype = channel_slice.dtype
    max_value = np.iinfo(datatype).max

    channel_slice = np.clip(channel_slice, lower_threshold, upper_threshold)

    channel_slice = channel_slice - lower_threshold
    thresholded_slice = np.rint(channel_slice/channel_slice.ptp() * max_value).astype(datatype)

    return thresholded_slice

