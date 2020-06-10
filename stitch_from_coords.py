from util import *

def stitch_from_coords(tissue_directory_regex, height, width, ordered_channels, filter_size = 8):

    round_subdirectory_string = "round*/"
    registered_coordinates_filename = "stitching_coordinates.registered.txt"
    round_directory_regex = os.path.join(tissue_directory_regex, round_subdirectory_string)

    MAX_INTENSITY = np.iinfo(np.uint16).max

    round_directories = glob.glob(round_directory_regex)

    max_coords = []

    for round_directory in round_directories:
        composite_directories = glob.glob(os.path.join(round_directory, "*", ""))
        num_channels = len(composite_directories)
        stitched_coordinates_path = os.path.join(round_directory, registered_coordinates_filename)
        _, max_x, max_y = parse_coordinates_file(stitched_coordinates_path)
        max_coords.append((max_x + width, max_y + height))

    min_global_width, min_global_height = np.amin(max_coords, axis = 0)

    for round_directory in round_directories[40:]:
        composite_directories = glob.glob(os.path.join(round_directory, "*", ""))
        num_channels = len(ordered_channels)
        stitched_coordinates_path = os.path.join(round_directory, registered_coordinates_filename)
        filename_to_coordinates, max_x, max_y = parse_coordinates_file(stitched_coordinates_path)
        
        canvas = np.zeros((max_y + height, max_x + width, num_channels), np.float64)
        #for composite_index, composite_directory in enumerate(composite_directories):
        #    print(composite_directory)
        #    channel_label, channel = os.path.basename(os.path.normpath(composite_directory)).split('.')

        for channel_index, channel in enumerate(ordered_channels):
            composite_directory_regex = round_directory + "*" + channel + "*"
            # composite_directory = glob.glob(composite_directory_regex)
            composite_directory = next(glob.iglob(composite_directory_regex))

            for filename in filename_to_coordinates:
                current_x, current_y = filename_to_coordinates[filename]
                source_image = imageio.imread(os.path.join(composite_directory, filename))
                canvas[current_y : current_y + height, current_x : current_x + width, channel_index] = source_image 
            
            
        reduced_canvas = normalize_and_convert_to_16_bit(canvas)
        filtered_reduced_canvas = median_filter(reduced_canvas, (filter_size, filter_size, 1)) 
        #print(np.sum(np.sum(filtered_reduced_canvas, axis=0), axis = 0))
        #print(filtered_reduced_canvas.shape)
        filtered_reduced_cropped_canvas = filtered_reduced_canvas[:min_global_height, :min_global_width]
        #print(filtered_reduced_cropped_canvas.shape)
        #print(filtered_reduced_cropped_canvas.shape)
        #print(filtered_reduced_canvas.ptp())
        imageio.imwrite(os.path.join(round_directory, "stitched.tiff"), filtered_reduced_cropped_canvas)

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--tissue-directory-regex', help='Regex that matches all directories of composite images that must be stitched')
    parser.add_argument('--height', help='Height of eah FOV in pixels', type=int)
    parser.add_argument('--width', help='Width of each FOV in pixels', type=int)
    parser.add_argument('--ordered-channels', help='Channels, in order from lowest to highest frequency.', nargs='+')
    parser.add_argument('--filter-size', help='Dimensions of median filter', type=int, default=8)
    args, _ = parser.parse_known_args()
   
    stitch_from_coords(args.tissue_directory_regex, args.height, args.width, args.ordered_channels, args.filter_size) 
