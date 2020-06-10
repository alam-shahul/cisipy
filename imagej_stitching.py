from util import *
import imagej

def imagej_stitching(tissue_directory_regex, cols, rows):

    round_subdirectory_string = "round*/"
    round_directory_regex = tissue_directory_regex + round_subdirectory_string

    round_directories = glob.glob(round_directory_regex)#[:6] 

    # ImageJ/Fiji setup
    ij = imagej.init('/home/unix/shahul/CTS/codeSource/Fiji.app')
    IJM_EXTENSION = ".ijm"
    STITCHING_MACRO = """
            #@ String sourceDirectory
            #@ String outputDirectory
            #@ int cols
            #@ int rows
    
            print(outputDirectory);
            function action(sourceDirectory, outputDirectory, genericFilename, filename, coordinateFilename) {
                run("Grid/Collection stitching", "type=[Grid: snake by rows] order=[Right & Down ] grid_size_x=" + cols + " grid_size_y=" + rows + " tile_overlap=6 first_file_index_i=0 directory=" + sourceDirectory + " file_names=" + genericFilename + " output_textfile_name=" + coordinateFilename + " fusion_method=[Linear Blending] regression_threshold=0.30 max/avg_displacement_threshold=2.50 absolute_displacement_threshold=3.50 subpixel_accuracy compute_overlap computation_parameters=[Save computation time (but use more RAM)] image_output=[Fuse and display]");
                saveAs("png", outputDirectory + filename);
                close();
            }
    
            action(sourceDirectory, outputDirectory, "fov_{i}.png", "reference_stitch", "../stitching_coordinates.txt");
            
            """
   
    for round_directory in round_directories:
        dapi_directory = glob.glob(os.path.join(round_directory, "DAPI*/"))[0]
        print(dapi_directory)
        args = {
                'sourceDirectory': dapi_directory,
                'outputDirectory': round_directory,
                'cols': cols,
                'rows': rows
        }
           
        result = ij.py.run_macro(STITCHING_MACRO, args)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--tissue-directory-regex', help='Paths to directories for each round for each tissue')
    parser.add_argument('--cols', help='Number of columns in mosaic of FOVs')
    parser.add_argument('--rows', help='Number of rows in mosaic of FOVs')
    args, _ = parser.parse_known_args()
    
    imagej_stitching(args.tissue_directory_regex, args.cols, args.rows)
