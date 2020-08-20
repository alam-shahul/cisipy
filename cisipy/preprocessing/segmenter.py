import numpy as np
import imageio
from scipy.ndimage import gaussian_filter
from scipy.sparse import csr_matrix, save_npz, load_npz

import subprocess
from cellprofiler_core import image, object, pipeline, preferences, workspace, measurement
preferences.set_headless()

from pathlib import Path, PurePath
import multiprocessing as mp

def segment_single_sample(sample, input_directory, output_directory):
    """
    """
    # TODO: add docstring

    sample_name = sample["name"]
    sample_input_subdirectory = input_directory / sample_name
    sample_output_subdirectory = output_directory / sample_name
    
    rounds = sample["rounds"]

    composite_filepaths, direct_filepaths = split_filepaths(rounds, sample_input_subdirectory)

    merged_composite_filepath = sample_input_subdirectory / "merged_composites.tif"
    merge_composites(composite_filepaths, merged_composite_filepath)
   
    # TODO: fix this to be better if possible?
    # Assume there is at least one round of imaging to get a filepath to one reference image
    initial_round = rounds[0]
    reference_channel_index = initial_round["reference_channel"]
    round_input_subdirectory = sample_input_subdirectory / "round1"
    reference_channel_name = initial_round["channels"][reference_channel_index]
    reference_image_filepath = (round_input_subdirectory / reference_channel_name).with_suffix( ".tif")

    print(__file__)
    segment(reference_image_filepath, merged_composite_filepath, sample_input_subdirectory, sample_output_subdirectory)
    aggregated_masks_filepath = sample_output_subdirectory / "composite_mask.tiff"
    sparse_masks_filepath = sample_output_subdirectory / "sparse_masks.npz"
    parse_and_save_cell_masks(aggregated_masks_filepath, sparse_masks_filepath)
   
    composite_measurements_filepath = sample_output_subdirectory / "composite_measurements.npy" 
    direct_measurements_filepath = sample_output_subdirectory / "direct_measurements.npy" 
    integrate_cells(sparse_masks_filepath, composite_filepaths, composite_measurements_filepath)
    integrate_cells(sparse_masks_filepath, direct_filepaths, direct_measurements_filepath)

def split_filepaths(rounds, input_directory):
    """
    """
    composite_filepaths = []
    direct_filepaths = []
    for round_index, imaging_round in enumerate(rounds, start=1):
        round_directory = ("round%d" % round_index)
        round_input_subdirectory = input_directory / round_directory

        channels = imaging_round["channels"]
        composite_channel_indices = imaging_round.get("composite_channels", [])
        reference_channel_index = imaging_round["reference_channel"]

        for channel_index, channel in enumerate(channels):
            if channel_index == reference_channel_index:
                continue
            elif channel_index in composite_channel_indices:
                composite_filepaths.append((round_input_subdirectory / channel).with_suffix( ".tif"))
            else:
                direct_filepaths.append((round_input_subdirectory / channel).with_suffix( ".tif"))

    composite_filepaths.sort(key=lambda filepath : filepath.name)
    direct_filepaths.sort(key=lambda filepath : filepath.name)

    return composite_filepaths, direct_filepaths

def segment_all_samples(config, parallelize=0):
    """
    """
    # TODO: write docstring

    workspace_directory = config["workspace_directory"]
    input_directory = Path(workspace_directory, "registered")
    output_directory = Path(workspace_directory, "segmented")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    if parallelize > 0:
        num_processes = mp.cpu_count()
        processes = []
        for sample in samples:
            process = mp.Process(target=segment_single_sample, args=(sample, input_directory, output_directory))
            process.start()
            processes.append(process)

        for process in processes:
            process.join()
    else:
        for sample in samples:
            segment_single_sample(sample, input_directory, output_directory)

def merge_composites(composite_filepaths, output_path):
    """
    """

    first_filepath, *other_filepaths = composite_filepaths

    merged_image = imageio.imread(first_filepath)
    for composite_filepath in other_filepaths:
        other_image = imageio.imread(composite_filepath)
        merged_image = np.maximum(merged_image, other_image)

    filtered_merged_image = gaussian_filter(merged_image, 4)  
    imageio.imwrite(output_path, filtered_merged_image)

    return filtered_merged_image
   
def segment(reference_image_filepath, merged_composite_filepath, input_directory, output_directory):
    """
    """
    # TODO: this is hacky. Consult with CellProfiler people to use the Python interface to create
    # a cell segmentation pipeline
    if __package__:
        with path(__package__, "segment.cppipe") as segmentation_macro_filepath:
            pipeline_filepath = segmentation_macro_filepath
    else:
        pipeline_filepath = str(PurePath(__file__).parent / "segment.cppipe")
    print(pipeline_filepath)
    subprocess.run(["cellprofiler", "-c", "-p", pipeline_filepath, "-i", input_directory, "-o", input_directory])
    subprocess.run(["mv", "output/composite_mask.tiff", output_directory])
    subprocess.run(["rm", "-rf", "output/"])
    
    # segmentation_pipeline = pipeline.Pipeline()
    # segmentation_pipeline.load("segment.cppipe")

    # image_set_list = image.ImageSetList()
    # image_set = image_set_list.get_image_set(0)

    # reference_image = imageio.imread(reference_image_filepath)
    # reference_handle = image.Image(reference_image)
    # merged_composite = imageio.imread(merged_composite_filepath)
    # merged_composite_handle = image.Image(merged_composite)

    # image_set.add("DAPI", reference_handle)
    # image_set.add("RNA", merged_composite_handle)
    # 
    # object_set = object.ObjectSet()

    # objects  = object.Objects()
    # 
    # object_set.add_objects(objects, "example")
    # measurements = measurement.Measurements()
    # 
    # segmentation_workspace = workspace.Workspace(
    #     segmentation_pipeline,
    #     None,
    #     image_set,
    #     object_set,
    #     measurements,
    #     image_set_list,
    # )
    # output_measurements = segmentation_pipeline.run(None)

def parse_and_save_cell_masks(input_path, output_path):
    """
    """
   
    aggregate_masks = imageio.imread(input_path)
    num_cells = np.unique(aggregate_masks).size
    flattened_masks = aggregate_masks.flatten()
    image_shape = flattened_masks.shape

    # TODO: this only works so far if there are a max of np.iinfo(np.uint16).max cell objects.
    # Amend so that it works for more as well???
    is_cell_index = (flattened_masks != 0)
    binary_mask_data = np.ones(shape=is_cell_index.sum(), dtype=np.float32)
    pixel_indices = is_cell_index.nonzero()
    mapping, cell_indices = np.unique(flattened_masks, return_inverse=True)
    #cell_indices = flattened_masks[pixel_indices] - 1

    compressed_cell_masks = csr_matrix((binary_mask_data, (cell_indices, *pixel_indices)), shape = (num_cells, *image_shape), dtype=np.float32)

    save_npz(output_path, compressed_cell_masks)

    return compressed_cell_masks

# def filter(im, filter_size):
#   if filter_size > 0:
#       if len(im.shape) == 3:
#           for i in range(im.shape[2]):
#               im[:,:,i] = ndimage.gaussian_filter(im[:,:,i], filter_size)
#       else:
#           im = ndimage.gaussian_filter(im, filter_size)
#   return im
# 
# if __name__ == '__main__':
#   parser = argparse.ArgumentParser()
#   parser.add_argument('--basepath', help='Path to directory with subdirs for parsed images in each tissue')
#   parser.add_argument('--tissues', help='Comma-separated list of tissue numbers to include')
#   parser.add_argument('--filter-size', help='Size of gaussian filter',type=float,default=4)
#   parser.add_argument('--stitched-subdir', help='Subdirectory with stitched images', default='stitched_aligned_filtered')
#   args,_ = parser.parse_known_args()
#   for t in args.tissues.split(','):
#       tissue = 'tissue%s' % t
#       FP = glob.glob(os.path.join(args.basepath,tissue,args.stitched_subdir,'Composite_*'))
#       im = imageio.imread(FP[0])
#       for fp in FP[1:]:
#           im = np.maximum(im,imageio.imread(fp))
#       im = filter(im, args.filter_size)
#       imageio.imwrite('%s/%s/%s/All_Composite.tiff' % (args.basepath,tissue,args.stitched_subdir),im)
#       print(tissue)
# if __name__ == '__main__':
#   parser = argparse.ArgumentParser()
#   parser.add_argument('--basepath', help='Path to directory with subdirs for parsed images in each tissue')
#   parser.add_argument('--tissues', help='Comma-separated list of tissue numbers to include')
#   parser.add_argument('--mask-file', help='Mask file (or prefix), eg ExpandedNuclei_* or DAPI.tiff', default='All_Composite.tiff')
#   args,_ = parser.parse_known_args()
#   for t in args.tissues.split(','):
#       tissue = 'tissue%s' % t
#       im = imageio.imread('%s/%s/segmented/%s' % (args.basepath,tissue,args.mask_file)).flatten()
#       col_ind = np.where(im > im.min())[0]
#       data = np.ones(len(col_ind),dtype=np.float32)
#       row_ind = im[col_ind].astype(np.int)-1
#       X = csr_matrix((data,(row_ind,col_ind)),shape=[len(np.unique(row_ind)),len(im)],dtype=np.float32)
#       save_npz('%s/%s/segmented/cell_masks.npz' % (args.basepath,tissue),X)
#       print(tissue,X.shape,len(data))

def integrate_cells(sparse_masks_filepath, image_filepaths, output_filepath):
    """
    """

    cell_masks = load_npz(sparse_masks_filepath)
    num_images = len(image_filepaths)
    num_cells = cell_masks.shape[0]
    measurements = np.zeros(shape=(num_images, num_cells), dtype=np.float32)
    for image_index, image_filepath in enumerate(image_filepaths):
        flattened_image = imageio.imread(image_filepath).flatten()
        integrated_intensities = cell_masks.dot(flattened_image)
        measurements[image_index] = integrated_intensities

    np.save(output_filepath, measurements)

    return measurements


# if __name__ == '__main__':
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--basepath', help='Path to directory with subdirs for parsed images in each tissue')
#     parser.add_argument('--tissues', help='Comma-separated list of tissue numbers to include')
#     parser.add_argument('--stitched-subdir', help='Subdirectory with stitched images', default='stitched_aligned_filtered')
#     parser.add_argument('--mask-basepath', help='Optional alternative basepath for cell masks', default=None)
#     parser.add_argument('--as-average', dest='as_average', action='store_true')
#     parser.add_argument('--binary', dest='binary', action='store_true')
#     parser.set_defaults(as_average=False)
#     parser.set_defaults(binary=False)
#     args,_ = parser.parse_known_args()
# 
#     CellMasks = load_npz('%s/%s/segmented/cell_masks.npz' % (args.mask_basepath,tissue))
#     # if args.as_average:
#     #     for i in range(CellMasks.shape[0]):
#     #         ii = CellMasks.indptr[i]
#     #         ij = CellMasks.indptr[i+1]
#     #         CellMasks.data[ii:ij] = 1/(ij-ii)
# 
#     FP = glob.glob(os.path.join(args.basepath,tissue,args.stitched_subdir,'*.tiff'))
#     FP_composites = [fp for fp in FP if 'Composite_' in fp.split('/')[-1]]
#     FP_direct = [fp for fp in FP if (('Composite_' not in fp.split('/')[-1]) and ('All_Composite' not in fp.split('/')[-1]) and ('DAPI' not in fp.split('/')[-1]) and ('merged' not in fp.split('/')[-1]))]
#     # sort the composites by number
#     FP_composites = [(int(fp.split('_')[-1].split('.')[0]),fp) for fp in FP_composites]
#     FP_composites = [fp[1] for fp in sorted(FP_composites)]
#     X = []
#     L = []
#     for fp in FP_composites:
#         im = imageio.imread(fp).flatten()
#         if args.binary:
#             im = (im > 0).astype(im.dtype)
#         X.append(CellMasks.dot(im))
#         L.append(fp.split('/')[-1].split('.')[0])
#     # if args.as_average:
#     #     if args.binary:
#     #         savepath = '%s/%s/average_intensity_binary' % (args.basepath,tissue)
#     #     else:
#     #         savepath = '%s/%s/average_intensity' % (args.basepath,tissue)
#     # else:
#     #     if args.binary:
#     #         savepath = '%s/%s/integrated_intensity_binary' % (args.basepath,tissue)
#     #     else:
#     #         savepath = '%s/%s/integrated_intensity' % (args.basepath,tissue)
#     savepath = '%s/%s/integrated_intensity' % (args.basepath,tissue)
#     _=os.system('mkdir %s' % savepath)
#     np.save('%s/composite_measurements.npy' % savepath,X)
#     # np.save('%s/composite_labels.npy' % savepath,L)
#     X = []
#     L = []
#     # get the size of cell masks
#     FP_mask = glob.glob(os.path.join(args.mask_basepath,tissue,'segmented','ExpandedNuclei_*'))
#     if len(FP_mask) == 0:
#         FP_mask = glob.glob(os.path.join(args.mask_basepath,tissue,'segmented','All_Composite.tiff'))
#     n = imageio.imread(FP_mask[0]).shape
#     for fp in FP_direct:
#         im = imageio.imread(fp)
#         # images might have been padded on the bottom and right
#         im = im[:n[0],:n[1]].flatten()
#         if args.binary:
#             im = (im > 0).astype(im.dtype)
#         X.append(CellMasks.dot(im))
#         L.append('.'.join(fp.split('/')[-1].split('.')[:-1]))
#     if (tissue == 'tissue2') and ('Foxp2' in L): # Foxp2 was measured twice in tissue2
#         gi = L.index('Foxp2')
#         X.append(X[gi])
#         L.append(L[gi])
#     if args.as_average:
#         np.save('%s/direct_measurements.npy' % savepath,X)
#         np.save('%s/direct_labels.npy' % savepath,L)
#     else:
#         np.save('%s/direct_measurements.npy' % savepath,X)
#         np.save('%s/direct_labels.npy' % savepath,L)
# 
# 
# 
# 
