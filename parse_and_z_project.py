from util import *

def parse_and_z_project(background_path_regex, source_path_regex, fov_order_map_path, context_to_channel_map_path, outpath):
    with open(context_to_channel_map_path, 'r') as handle:
        context_to_channel_map = json.load(handle)
    
    MAX_INTENSITY = np.iinfo(np.uint16).max
   

    background_filepaths = sorted(glob.glob(background_path_regex), key = lambda filepath: filepath.split('/')[-1])
    source_filepaths = sorted(glob.glob(source_path_regex), key = lambda filepath: filepath.split('/')[-1])
   
    fov_order_map = np.load(fov_order_map_path)

    data_for_filepath = {}

    # TODO: Why does it have to be sorted?
    for filepath in (source_filepaths + background_filepaths)[40:]:
        filename = os.path.splitext(filepath)[0]
        relative_filename = filename[filename.rfind('/')+1:].split()
        tissue = ''.join(relative_filename[1:3])
        round_number = ''.join(relative_filename[3:5])
        
        print("Processing nd2 file %s" % filepath)
        file_data = parse_nd2_file(filepath)

        source_images, coordinate_pairs, fields_of_view, channels, microns_per_pixel = [file_data[key] for key in ['aggregated_images', 'coordinate_pairs', 'fields_of_view', 'channels', 'microns_per_pixel']]
        num_fov, num_channels, num_rows, num_columns = source_images.shape

        for channel_index, channel in enumerate(channels):
            for fov_index, fov in enumerate(fields_of_view):
                source_image = source_images[fov_index, channel_index]

                #reduced_source_image = normalize_and_convert_to_16_bit(source_image)
                reduced_source_image = source_image

                if channel == 'conf-405':
                    channel_label = 'DAPI_%s' % round_number
                    context_to_channel_map[tissue][round_number][channel] = channel_label
                else:
                    channel_label = context_to_channel_map[tissue][round_number][channel]
                
                with open(context_to_channel_map_path, 'w') as handle:
                    json.dump(context_to_channel_map, handle, sort_keys=True, indent=4)

                os.makedirs(outpath + '/%s/images/%s/%s.%s' % (tissue, round_number, channel_label, channel), exist_ok=True)
                imageio.imwrite(outpath + '/%s/images/%s/%s.%s/fov_%d.png' % (tissue, round_number, channel_label, channel, fov_index), reduced_source_image)
                os.makedirs(outpath + '/%s/arrays/%s/%s.%s' % (tissue, round_number, channel_label, channel), exist_ok=True)
                np.save(outpath + '/%s/arrays/%s/%s.%s/fov_%d.png' % (tissue, round_number, channel_label, channel, fov_index), reduced_source_image)


if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--background-path-regex', help='Paths to files containing background .nd2 images')
    parser.add_argument('--source-path-regex', help='Paths to files containing source .nd2 files')
    parser.add_argument('--fov-order-map-path', help='.npy array with relative locations of each field-of-view')
    parser.add_argument('--context-to-channel-map-path', help='Path to .pickle file representing map from round to field-of-view')
    parser.add_argument('--outpath', help='Output path')
    args, _ = parser.parse_known_args()
   
    parse_and_z_project(args.background_path_regex, args.source_path_regex, args.fov_order_map_path, args.context_to_channel_map_path, args.outpath)
