from util import *

def subtract_background(tissue_directory_regex, ordered_channels, background_scaling_factors, blank_round_number):
    round_subdirectory_regex = "round*/"
    blank_round_string = "round%d/" % blank_round_number
    stitched_filename = "stitched.tiff"
    background_subtracted_filename = "background_subtracted.tiff"

    ordered_factors = np.array([background_scaling_factors[channel] for channel in ordered_channels])

    tissue_directories = glob.glob(tissue_directory_regex)

    for tissue_directory in tissue_directories:
        print(tissue_directory)
        round_directory_regex = tissue_directory + round_subdirectory_regex
        round_directories = glob.glob(round_directory_regex)
        blank_round_directory = os.path.join(tissue_directory, blank_round_string)
        blank_round_image_filepath = os.path.join(blank_round_directory, stitched_filename)
        blank_round_image = imageio.imread(blank_round_image_filepath)
        blank_round_dapi = blank_round_image[:, :, 0]

        for round_directory in round_directories:
            #print(round_directory)
            if round_directory == blank_round_directory:
                continue
            round_image_filepath = os.path.join(round_directory, stitched_filename)
            round_image = imageio.imread(round_image_filepath)
            round_dapi = round_image[:, :, 0]
            
            shift = find_shift(round_dapi, blank_round_dapi, scale = 0.1)
            print("Applying shift...")
            shifted_blank_image = apply_shifts(blank_round_image, shift)

            background_subtracted_image = np.clip(round_image - shifted_blank_image * ordered_factors, 0, None)
            background_subtracted_image[:, :, 0] = round_dapi

            background_subtracted_image = background_subtracted_image.astype(np.uint16)

            new_filepath = os.path.join(round_directory, background_subtracted_filename)
            imageio.imwrite(new_filepath, background_subtracted_image)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tissue-directory-regex', help="Regex that matches tissue directories.")
    parser.add_argument('--ordered-channels', help='Channels, in order from lowest to highest frequency.', nargs='+')
    parser.add_argument('--background-scaling-factors', help='Factors to multiply blanks before subtraction (by channel)',default='1.5,1.15,1.35')
    parser.add_argument('--blank-round-number', help="Round that contains blank images.", type=int)
    parser.set_defaults(save_stitched=False)
    args,_ = parser.parse_known_args()

    subtract_background(args.tissue_directory_regex, args.ordered_channels, args.background_scaling_factors, args.blank_round_number)
