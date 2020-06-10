from util import *

def register_and_tile_images(tissue_directory_regex, tile_size, blank_round_number):
    round_subdirectory_regex = "round*/"
    blank_round_string = "round%d/" % blank_round_number
    corrected_filename = "flat_field_corrected.tiff"
    registered_filename = "registered.tiff"

    tissue_directories = glob.glob(tissue_directory_regex)

    for tissue_directory in tissue_directories:
        Images = []
        #print(tissue_directory)
        round_directory_regex = tissue_directory + round_subdirectory_regex
        blank_round_directory = os.path.join(tissue_directory, blank_round_string)
        round_directories = [directory for directory in glob.glob(round_directory_regex) if directory != blank_round_directory]

        for round_directory in round_directories:
            round_image_filepath = os.path.join(round_directory, corrected_filename)
            round_image = imageio.imread(round_image_filepath)
            Images.append(round_image)
        
        min_shape = (min(im.shape[0] for im in Images), min(im.shape[1] for im in Images))
        Images = np.array([im[:min_shape[0],:min_shape[1]] for im in Images])
       
        # TODO: How to calculate dapi index? It's zero for now
        dapi_slices = Images[:, :, :, 0]
        first_dapi = dapi_slices[0]
        shifts = find_all_shifts(first_dapi, dapi_slices)
        print("Shifts calculated.")
        ImagesAligned = np.array([apply_shifts(Images[index], shifts[index]) for index in range(len(Images))])
        ImagesAligned = crop_all_shifted(ImagesAligned, shifts)

        for round_index, round_directory in enumerate(round_directories):
            print(round_directory)
            round_output_filepath = os.path.join(round_directory, registered_filename)
            round_output_image = ImagesAligned[round_index]
            imageio.imwrite(round_output_filepath, ImagesAligned[round_index])
            #max_value = np.iinfo(Images[0].dtype).max
            #round_output_image = ormalize_image_scale(round_output_image, max_value)

            os.makedirs(os.path.join(round_directory, "tiles"), exist_ok=True)
            tiles, new_fov_pattern = tilify(ImagesAligned[round_index], tile_size)
            for tile, new_fov in zip(tiles, new_fov_pattern.flatten()):
                array_filepath = os.path.join(round_directory, "tiles", "fov_%d.npy" % new_fov)
                np.save(array_filepath, tile)
                image_filepath = os.path.join(round_directory, "tiles", "fov_%d.tiff" % new_fov)
                imageio.imwrite(image_filepath, tile)
            np.save(os.path.join(round_directory, "tiles", "modified_fov_pattern.npy"), new_fov_pattern)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tile-size', help='Size of output images',type=int,default=1024)
    parser.add_argument('--tissue-directory-regex', help='Path to directory with subdirs for parsed images in each tissue')
    parser.add_argument('--blank-round-number', help='Path to directory with subdirs for parsed images in each tissue')
    parser.set_defaults(save_tiles=False)
    parser.set_defaults(save_stitched=False)
    args, _ = parser.parse_known_args()

    register_and_tile_images(args.tissue_directory_regex, args.tile_size, args.blank_round+number)
