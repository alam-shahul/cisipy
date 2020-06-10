from util import *

def calculate_and_apply_flat_field_correction(tissue_directory_regex, blank_round_number, height, width, filter_width):
    round_subdirectory_regex = "round*/"
    registered_coordinates_filename = "stitching_coordinates.registered.txt"
    blank_round_string = "round%d/" % blank_round_number
    thresholded_filename = "thresholded.tiff"
    corrected_filename = "flat_field_corrected.tiff"

    fov_cutouts = []
    fov_count = 0
    tissue_directories = glob.glob(tissue_directory_regex)
    #FP_blanks = glob.glob(os.path.join(tissue_directory_regex, '*', args.blank_round, registered_coordinates_filename))
    for tissue_directory in tissue_directories:
        round_directory_regex = tissue_directory + round_subdirectory_regex
        round_directories = glob.glob(round_directory_regex)
        blank_round_directory = os.path.join(tissue_directory, blank_round_string)

        for round_directory in round_directories:
            print(round_directory)
            if round_directory == blank_round_directory:
                continue

            stitched_coordinates_filepath = os.path.join(round_directory, registered_coordinates_filename)
            filename_to_coordinates, max_x, max_y = parse_coordinates_file(stitched_coordinates_filepath)
            round_image_filepath = os.path.join(round_directory, thresholded_filename)
            round_image = imageio.imread(round_image_filepath)

            for filename in filename_to_coordinates:
                current_x, current_y = filename_to_coordinates[filename]
                padded_cutout = np.zeros((height, width, round_image.shape[2]))
                cutout = round_image[current_y : current_y + height, current_x : current_x + width]
                actual_height, actual_width, _ = cutout.shape
                padded_cutout[:actual_height, :actual_width] = cutout
                fov_cutouts.append(padded_cutout)

    #fov_cutouts = np.array(fov_cutouts)
    filter_sigma = height // filter_width
    #fov_median = np.zeros(fov_cutouts[0].shape)
    #for channel_index in range(4):
    #    fov_median[:, :, channel_index] = np.median([cutout[:, :, channel_index] for cutout in fov_cutouts], axis = 0)
    #    print("calculating median")
    fov_median = np.median(fov_cutouts, axis = 0) 
    print("calculated median")
    flat_field = gaussian_filter(fov_median, filter_sigma)

    print('done calculating flat field')

    inverse_field = 1/flat_field
    inverse_field /= inverse_field.max()
    
    for tissue_directory in tissue_directories:
        round_directory_regex = tissue_directory + round_subdirectory_regex
        round_directories = glob.glob(round_directory_regex)
        blank_round_directory = os.path.join(tissue_directory, blank_round_string)

        for round_directory in round_directories:
            if round_directory == blank_round_directory:
                continue
            np.save('%s/flat_field.npy' % round_directory, flat_field)
            imageio.imsave('%s/flat_field.tiff' % round_directory, flat_field.astype(np.uint16))
            #print(round_directory)

            stitched_coordinates_filepath = os.path.join(round_directory, registered_coordinates_filename)
            filename_to_coordinates, max_x, max_y = parse_coordinates_file(stitched_coordinates_filepath)
            round_image_filepath = os.path.join(round_directory, thresholded_filename)
            round_image = imageio.imread(round_image_filepath)
            corrected_round_image = np.zeros(round_image.shape)

            for filename in filename_to_coordinates:
                current_x, current_y = filename_to_coordinates[filename]
                fov = round_image[current_y : current_y + height, current_x : current_x + width]
                #print(fov.shape)
                corrected_round_image[current_y : current_y + height, current_x : current_x + width] = fov * inverse_field[:fov.shape[0], :fov.shape[1]]

            corrected_round_image = corrected_round_image.astype(np.uint16)    
            #print(corrected_round_image.shape)
            corrected_filepath = os.path.join(round_directory, corrected_filename)
            imageio.imwrite(corrected_filepath, corrected_round_image)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tissue-directory-regex', help='Path to directory with subdirs for parsed images in each tissue')
    parser.add_argument('--blank-round-number', help='Round in which blank images were collected (skip these)')
    parser.add_argument('--height', help='Pixels along each dimension of one fov',type=int,default=2048)
    parser.add_argument('--width', help='Pixels along each dimension of one fov',type=int,default=2048)
    parser.add_argument('--filter-width', help='Width of flat field gaussian_filter; eg 16 -> 1/16th of image size',type=int,default=8)
    args,_ = parser.parse_known_args()

    calculate_and_apply_flat_field_correction(args.tissue_directory_regex, args.blank_round_number, args.height, args.width, args.filter_width)
