import numpy as np
import imageio
from scipy.ndimage import gaussian_filter
from functools import reduce
from pathlib import Path
import multiprocessing as mp

def merge_composites_single_sample(sample, input_directory):
    """
    """
    # TODO: add docstring

    sample_name = sample["name"]
    sample_input_subdirectory = input_directory / sample_name
    
    rounds = sample["rounds"]

    composite_filepaths = []
    for round_index, imaging_round in enumerate(rounds, start=1):
        round_directory = ("round%d" % round_index)
        round_input_subdirectory = sample_input_subdirectory / round_directory

        channels = imaging_round["channels"]
        composite_channel_indices = imaging_round.get("composite_channels", [])

        for channel_index in composite_channel_indices:
            composite_filepaths.append((round_input_subdirectory / channels[channel_index]).with_suffix( ".tif"))

    first_filepath, *other_filepaths = composite_filepaths

    merged_image = imageio.imread(first_filepath)
    for composite_filepath in other_filepaths:
        other_image = imageio.imread(composite_filepath)
        merged_image = np.maximum(merged_image, other_image)

    filtered_merged_image = gaussian_filter(merged_image, 4) 
    imageio.imwrite(sample_input_subdirectory / "merged_composites.tif", filtered_merged_image)

    return filtered_merged_image

def merge_composites_all_samples(config, parallelize=0):
    """
    """
    # TODO: write docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(workspace_directory, "registered")

    samples = config["samples"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    if parallelize > 0:
        num_processes = mp.cpu_count()
        processes = []
        for sample in samples:
            process = mp.Process(target=merge_composites_single_sample, args=(sample, input_directory))
            process.start()
            processes.append(process)

        for process in processes:
            process.join()
    else:
        for sample in samples:
            merge_composites_single_sample(sample, input_directory)

# def filter(im, filter_size):
# 	if filter_size > 0:
# 		if len(im.shape) == 3:
# 			for i in range(im.shape[2]):
# 				im[:,:,i] = ndimage.gaussian_filter(im[:,:,i], filter_size)
# 		else:
# 			im = ndimage.gaussian_filter(im, filter_size)
# 	return im
# 
# if __name__ == '__main__':
# 	parser = argparse.ArgumentParser()
# 	parser.add_argument('--basepath', help='Path to directory with subdirs for parsed images in each tissue')
# 	parser.add_argument('--tissues', help='Comma-separated list of tissue numbers to include')
# 	parser.add_argument('--filter-size', help='Size of gaussian filter',type=float,default=4)
# 	parser.add_argument('--stitched-subdir', help='Subdirectory with stitched images', default='stitched_aligned_filtered')
# 	args,_ = parser.parse_known_args()
# 	for t in args.tissues.split(','):
# 		tissue = 'tissue%s' % t
# 		FP = glob.glob(os.path.join(args.basepath,tissue,args.stitched_subdir,'Composite_*'))
# 		im = imageio.imread(FP[0])
# 		for fp in FP[1:]:
# 			im = np.maximum(im,imageio.imread(fp))
# 		im = filter(im, args.filter_size)
# 		imageio.imwrite('%s/%s/%s/All_Composite.tiff' % (args.basepath,tissue,args.stitched_subdir),im)
# 		print(tissue)
