import numpy as np
from collections import defaultdict
from skimage.registration import phase_cross_correlation
from skimage.transform import rescale
from scipy.ndimage import fourier_shift
import imageio

import multiprocessing as mp
from pathlib import Path

# def parse_rounds(fp):
#     Rounds2Channels = defaultdict(list)
#     f = open(fp,encoding='utf-8')
#     header = f.readline()
#     for line in f:
#         ls = line.strip().split(',')
#         Rounds2Channels[(ls[0],ls[1])].append(ls[2])
#     f.close()
#     return Rounds2Channels

def find_all_shifts(reference_image, other_images):
    """
    """

    shifts = []
    for other_image in other_images:
        shifts.append(find_shift(reference_image, other_image))

    return shifts

def find_shift(reference_image, other_image, scale=0.25):
    """
    """
    # TODO: Fill out docstring. Also why is there a scale parameter here? Is it to save computation?
    
    rescaled_reference_image = rescale(reference_image, scale)
    rescaled_other_image = rescale(other_image, scale)
    shift, error, diffphase = phase_cross_correlation(rescaled_reference_image, rescaled_other_image)
    scaled_shift = shift / scale

    return scaled_shift

def find_and_apply_shifts(ref_image,other_images,dapi_index,block_size=500,block_pad=250):
    im1 = ref_image[:,:,dapi_index]
    ImagesAligned = [ref_image.astype(np.float32)]
    for im2 in other_images:
        im2_shift = np.zeros(im2.shape,dtype=np.float32)
        for i in range(0,im1.shape[0],block_size):
            for j in range(0,im1.shape[1],block_size):
                im1_block = im1[max(0,i-block_pad):i+block_size+block_pad,max(0,j-block_pad):j+block_size+block_pad]
                im2_block = im2[i:i+block_size,j:j+block_size]
                if (im1_block.sum() > 0) and (im2_block.sum() > 0):
                    pad0 = im1_block.shape[0] - im2_block.shape[0]
                    pad1 = im1_block.shape[1] - im2_block.shape[1]
                    pad0 = (int(pad0/2), int(pad0/2 + pad0%2))
                    pad1 = (int(pad1/2), int(pad1/2 + pad1%2))
                    im2_block = np.pad(im2_block, (pad0, pad1, (0,0)), 'constant').astype(im1_block.dtype)
                    shift, error, diffphase = phase_cross_correlation(im1_block, im2_block[:,:,dapi_index])
                    offset_image = apply_shift_to_stack(im2_block,shift)
                    im2_shift[max(0,i-block_pad):i+block_size+block_pad,max(0,j-block_pad):j+block_size+block_pad] += offset_image
        ImagesAligned.append(im2_shift)
    return ImagesAligned

def apply_shift_to_stack(stack, shift):
    shifting_function = lambda layer: np.fft.ifftn(fourier_shift(np.fft.fftn(layer), shift))
    shifted_stack = np.zeros(stack.shape)

    for channel_index in range(stack.shape[-1]):
        shifted_stack[..., channel_index] = shifting_function(stack[..., channel_index])

    return shifted_stack.astype(np.float32)

def apply_shift(image, shift):
    shifted_image = np.fft.ifftn(fourier_shift(np.fft.fftn(image), shift))

    return shifted_image.real.astype(np.uint16)

def get_shift_crop_index(shifts):
    minimum_shifts = np.min(shifts, axis = 0).astype(np.int)
    maximum_shifts = np.max(shifts, axis = 0).astype(np.int)

    print(shifts)
    print(minimum_shifts)
    print(maximum_shifts)

    x_index = slice(None if maximum_shifts[0] <= 0 else maximum_shifts[0], None if minimum_shifts[0] >= 0 else minimum_shifts[0])
    y_index = slice(None if maximum_shifts[1] <= 0 else maximum_shifts[1], None if minimum_shifts[1] >= 0 else minimum_shifts[1])

    # crop_index = tuple(slice(None if maximum_shifts[index] <= 0 else maximum_shifts[index],
    #                          None if minimum_shifts[index] >= 0 else minimum_shifts[index])
    #                          for index in range(shifts.shape[1]))
    #                   ) 
    # if min_s[0] < 0:
    #   images = images[:min_s[0]]
    # if max_s[0] > 0:
    #   images = images[max_s[0]:]
    # if min_s[1] < 0:
    #   images = images[:,:min_s[1]]
    # if max_s[1] > 0:
    #   images = images[:,max_s[1]:]
    crop_index = (x_index, y_index)

    return crop_index

def normalize_image_scale(im,max_value,thresh_each=False):
    if thresh_each:
        for i in range(im.shape[-1]):
            thresh = np.percentile(im,max_value)
            im[:,:,i][im[:,:,i] > thresh] = thresh
            im[:,:,i] = im[:,:,i]/thresh
        return im.astype(np.float32)
    else:
        return (im/max_value).astype(np.float32)

def break_into_tiles(im,tile_size):
    tiles = []
    tile_pattern = []
    ti = 0
    for i in range(0,im.shape[0],tile_size):
        tile_row = []
        for j in range(0,im.shape[1],tile_size):
            x = im[i:i+tile_size, j:j+tile_size]
            x = np.pad(x, [(0,tile_size-x.shape[0]), (0,tile_size-x.shape[1]), (0,0)], 'constant')
            tiles.append(x)
            tile_row.append(ti)
            ti += 1
        if len(tile_row) > 0:
            tile_pattern.append(tile_row)
    return tiles,tile_pattern

# def rescale_intensities(Images,max_value,dapi_index,eps=1e-4, ptile=95):
#   # rescale all the measurements in each channel according to the min,max in that channel
#   Images = np.array(Images)
#   num_channels = Images.shape[-1]
#   I = Images.reshape([-1,num_channels])
#   channel_min = np.zeros(num_channels)
#   channel_max = np.zeros(num_channels)
#   for i in range(num_channels):
#       if i == dapi_index:
#           channel_min[i] = 0
#           channel_max[i] = I[:,i].max()
#       else:
#           channel_min[i] = np.percentile(I[:,i][I[:,i] > eps], 100-ptile)
#           channel_max[i] = np.percentile(I[:,i][I[:,i] > eps], ptile)
#   print(channel_min)
#   print(channel_max)
#   Images = (Images - channel_min)/channel_max
#   Images[Images < 0] = 0
#   Images[Images > 1] = 1
#   return Images*max_value

def rescale_16bit(image):
    """
    """
    # TODO: Considering reworking to be robust for bright/dark spots
    ii16 = np.iinfo(np.uint16)

    float_precision_image = image.astype(np.float32)
    rescaled_image = (float_precision_image - float_precision_image.min()) / float_precision_image.max()
    #print(ii16.max)
    #print(rescaled_image.max())

    return (rescaled_image * ii16.max).astype(np.uint16)

def register_images_all_samples(config, parallelize=0):
    """
    """
    # TODO: write docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(workspace_directory, "spots_only")
    output_directory = Path(workspace_directory, "registered")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    if parallelize > 0:
        num_processes = mp.cpu_count()
        print(num_processes)
        processes = []
        for sample in samples:
            process = mp.Process(target=register_images_single_sample, args=(sample, input_directory, output_directory))
            process.start()
            processes.append(process)

        for process in processes:
            process.join()
    else:
        for sample in samples:
            register_images_single_sample(sample, input_directory, output_directory)

def register_images_single_sample(sample, input_directory, output_directory):
    """
    """
    # TODO: write docstring
    
    sample_name = sample["name"]

    sample_input_subdirectory = input_directory / sample_name
    sample_output_subdirectory = output_directory / sample_name
    sample_output_subdirectory.mkdir(exist_ok=True)

    def build_reference_image_stack(rounds):
        """
        Helper function.
        """

        reference_filepaths = []
        for round_index, imaging_round in enumerate(rounds, start=1):
            round_directory = ("round%d" % round_index)
            round_input_subdirectory = sample_input_subdirectory / round_directory
            # round_input_subdirectory.mkdir(exist_ok=True)

            channels = imaging_round["channels"]
            reference_channel_index = imaging_round["reference_channel"]

            reference_filepaths.append((round_input_subdirectory / channels[reference_channel_index]).with_suffix( ".tif"))

        reference_image_stack = [imageio.imread(reference_filepath) for reference_filepath in reference_filepaths]

        # Crop all reference images to same size
        cropped_shape = tuple(np.array([image.shape for image in reference_image_stack]).min(axis = 0))
        print(cropped_shape)
        shape_crop_index = (slice(0, cropped_shape[0]), slice(0, cropped_shape[1]))

        reference_image_stack = np.stack([reference_image[shape_crop_index] for reference_image in reference_image_stack])
        print(reference_image_stack.shape)

        return reference_image_stack, shape_crop_index

    rounds = sample["rounds"]
    reference_image_stack, shape_crop_index = build_reference_image_stack(rounds)

    first_reference, *other_references = reference_image_stack
    required_shifts = [(0, 0)] + [find_shift(first_reference, other_reference) for other_reference in other_references]
    shift_crop_index = get_shift_crop_index(required_shifts)

    for round_index, imaging_round in enumerate(rounds, start=1):
        shift_index = round_index - 1
        round_directory = ("round%d" % round_index)
        channels = imaging_round["channels"]
        round_input_subdirectory = sample_input_subdirectory / round_directory
        round_output_subdirectory = sample_output_subdirectory / round_directory
        round_output_subdirectory.mkdir(exist_ok=True)

        # round_stack = build_round_stack(imaging_round, sample_input_subdirectory)
        # shifted_round_stack = apply_shift_to_stack(round_stack, required_shifts[round_index])

        for channel in channels:
            channel_filename = channel + ".tif"
            input_path = round_input_subdirectory / channel_filename
            output_path = round_output_subdirectory / channel_filename

            channel_image = imageio.imread(input_path)[shape_crop_index]
            registered_image = apply_shift(channel_image, required_shifts[shift_index])
            cropped_registered_image = registered_image[shift_crop_index]

            print(shape_crop_index)
            print(shift_crop_index)
            print(registered_image.shape)
            print(cropped_registered_image.shape)

            # TODO: Originally, we rescaled the intensity. Do we want to keep that here?
            scaled_image = rescale_16bit(cropped_registered_image)

            imageio.imwrite(output_path, scaled_image)

# def register_images_single_sample(basepath, tile_size=256, rounds_to_channels, dapi_index=3, processed_filename='DAPI.tiff', tmppath=None, rescale_intensity=True, save_tiles=True, save_stitched=True, shift_blocks=True):
#     """
#     Register images across multiple rounds in a single tissue sample.
# 
#     """
# 
#     pass
# 
# if __name__ == '__main__':
#   parser = argparse.ArgumentParser()
#   parser.add_argument('--basepath', help='Path to directory with subdirs for parsed images in each tissue')
#   parser.add_argument('--tissues', help='Comma-separated list of tissue numbers to include')
#   parser.add_argument('--tile-size', help='Size of output images',type=int,default=256)
#   parser.add_argument('--rounds-to-channels', help='CSV list of tissue, round, composition labels')
#   parser.add_argument('--dapi-index', help='Channel index for DAPI images',type=int,default=3)
#   parser.add_argument('--processed-filename', help='Name of processed files, or eg DAPI.tiff if separated by channel',default='DAPI.tiff')
#   parser.add_argument('--tmppath', help='Tmp path to store arrays_aligned_filtered',default=None)
#   parser.add_argument('--rescale-intensity',help='Rescale pixel intensities according the (nonzero) 1st,99th ptile observed in each channel', dest='rescale_intensity', action='store_true')
#   parser.add_argument('--save-tiles', dest='save_tiles', action='store_true')
#   parser.add_argument('--save-stitched', dest='save_stitched', action='store_true')
#   parser.add_argument('--shift-blocks',help='Find shifts in blocks. Used when stitching has failed in some round.', dest='shift_blocks', action='store_true')
#   parser.set_defaults(rescale_intensity=False)
#   parser.set_defaults(save_tiles=False)
#   parser.set_defaults(save_stitched=False)
#   parser.set_defaults(shift_blocks=False)
#   args,_ = parser.parse_known_args()
# 
#   Rounds2Channels = parse_rounds(args.rounds_to_channels)
#   for tissue_index in args.tissues.split(','):
#       tissue = 'tissue%s' % tissue_index
#       dapi_filepaths = glob.glob(os.path.join('%s/%s/round*/%s' % (args.basepath,tissue,args.processed_filename)))
#       dapi_filepaths = sorted(dapi_filepaths)
# 
#       dapi_images = [imageio.imread(dapi_filepath) for dapi_filepath in dapi_filepaths]
# 
#       if 'DAPI' in args.processed_filename:
#           for index in range(len(dapi_filepaths)):
#               round = dapi_filepaths[index].split('/')[-2]
#               channels = Rounds2Channels[(tissue,round)]
#               im = [imageio.imread(dapi_filepaths[index].replace('DAPI', channel)) for channel in channels]
#               im.insert(args.dapi_index, dapi_images[index])
#               dapi_images[i] = np.transpose(im, axes=(1,2,0))
# 
#         # Cut out reference images to all be the same size (TODO: is this necessary?)
#       min_shape = (min(im.shape[0] for im in dapi_images), min(im.shape[1] for im in dapi_images))
#       dapi_images = [im[:min_shape[0], :min_shape[1]] for im in dapi_images]
# 
#       if args.shift_blocks:
#           ImagesAligned = find_and_apply_shift_to_stack(dapi_images[0], dapi_images[1:], args.dapi_index)
#       else:
#           Images1 = [im[:,:,args.dapi_index] for im in dapi_images]
#           shifts = find_all_shifts(Images1[0],Images1[1:])
#           ImagesAligned = []
#           for i,im in enumerate(dapi_images):
#               if i == 0:
#                   ImagesAligned.append(im.astype(np.float32))
#               else:
#                   ImagesAligned.append(apply_shift_to_stack(im,shifts[i-1]))
#           ImagesAligned = [crop_all_shifted(images,shifts) for images in ImagesAligned]
#       
#         # Rescaling all intensities to lie in the range of 0-1
#         max_value = np.iinfo(dapi_images[0].dtype).max
# 
#       if args.rescale_intensity:
#           ImagesAligned = rescale_intensities(ImagesAligned,max_value,args.dapi_index)
# 
#       if args.save_stitched:
#           _=os.system('mkdir %s/%s/stitched_aligned_filtered' % (args.basepath,tissue))
#           for images,filepath in zip(ImagesAligned,dapi_filepaths):
#               chan_idx = np.where(images.reshape([-1,images.shape[-1]]).sum(0) > 0)[0]
#               im = images[:,:,chan_idx]
#               round = filepath.split('/')[-2]
#               channels = Rounds2Channels[(tissue,round)]
#               if (round == 'round1') and ('DAPI' not in channels):
#                   channels.insert(args.dapi_index,'DAPI')
#               for i,c in enumerate(channels):
#                   imageio.imwrite('%s/%s/stitched_aligned_filtered/%s.tiff' % (args.basepath,tissue,c), np.rint(im[:,:,i]).astype(dapi_images[0].dtype))
# 
#       if args.save_tiles:
#           if args.tmppath is None:
#               array_path = args.basepath
#           else:
#               array_path = args.tmppath
#               _=os.system('mkdir %s/%s' % (array_path,tissue))
#           _=os.system('mkdir %s/%s/arrays_aligned_filtered' % (array_path,tissue))
#           for images, filepath in zip(ImagesAligned,dapi_filepaths):
#               images = normalize_image_scale(images,max_value)
#               chan_idx = np.where(images.reshape([-1,images.shape[-1]]).sum(0) > 0)[0]
#               im = images[:, :, chan_idx]
#               round = filepath.split('/')[-2]
#            e  channels = Rounds2Channels[(tissue,round)]
#               if (round == 'round1') and ('DAPI' not in channels):
#                   channels.insert(args.dapi_index,'DAPI')
#               tiles, new_fov_pattern = break_into_tiles(im,args.tile_size)
#               new_fov_pattern = np.array(new_fov_pattern)
#               for tile, new_fov in zip(tiles,new_fov_pattern.flatten()):
#                   for i,c in enumerate(channels):
#                       #new_path = '%s/%s/arrays_aligned_filtered/fov_%d.%s.npy' % (args.basepath,tissue,new_fov,c)
#                       #np.save(new_path,tile[:,:,i])
#                       new_path = '%s/%s/arrays_aligned_filtered/fov_%d.%s.tiff' % (array_path,tissue,new_fov,c)
#                       imageio.imwrite(new_path,tile[:,:,i])
#               np.save('%s/%s/modified_fov_pattern.npy' % (args.basepath,tissue), new_fov_pattern)
#       print(tissue)
