#@ String basePath
#@ String filename
#@ String fusePath

print("Loading dataset!");

print(basePath + filename + ".ome.tif");

inputFilename = basePath + filename;
inputFilepath = inputFilename + ".ome.tif";

// define dataset
run("Define dataset ...",
	"define_dataset=[Automatic Loader (Bioformats based)]" +
	" project_filename=" + filename + ".xml path=" + inputFilepath + " exclude=10" +
	" bioformats_series_are?=Tiles move_tiles_to_grid_(per_angle)?=[Do not move Tiles to Grid (use Metadata if available)]" +
	" how_to_load_images=[Re-save as multiresolution HDF5] dataset_save_path=" + basePath +
	" subsampling_factors=[{ {1,1,1}, {2,2,1} }]" +
	" hdf5_chunk_sizes=[{ {32,32,4}, {16,16,16} }]" +
	" timepoints_per_partition=1" +
	" setups_per_partition=0" +
	" use_deflate_compression" +
	" export_path=" + inputFilename);

print("Finished dataset definition!");

// calculate pairwise shifts
run("Calculate pairwise shifts ...",
	"select=" + inputFilename + ".xml" +
	" process_angle=[All angles]" +
	" process_channel=[All channels]" +
	" process_illumination=[All illuminations]" +
	" process_tile=[All tiles]" +
	" process_timepoint=[All Timepoints]" +
	" method=[Phase Correlation]" +
	" channels=[use Channel conf-405]" +
	" downsample_in_x=2" +
	" downsample_in_y=2" +
	" downsample_in_z=1");

// filter shifts
run("Filter pairwise shifts ...",
	"select=" + inputFilename + ".xml" +
	" filter_by_link_quality" +
	" min_r=0.5" +
	" max_r=1" +
	" max_shift_in_x=0" +
	" max_shift_in_y=0" +
	" max_shift_in_z=0" +
	" max_displacement=0");

// Global optimize and apply
run("Optimize globally and apply shifts ...",
	"select=" + inputFilename + ".xml" +
	" process_angle=[All angles]" +
	" process_channel=[All channels]" +
	" process_illumination=[All illuminations]" +
	" process_tile=[All tiles]" +
	" process_timepoint=[All Timepoints]" +
	" relative=2.500" +
	" absolute=3.500" +
	" global_optimization_strategy=[Two-Round using Metadata to align unconnected Tiles]" +
	" fix_group_0-0");

// fuse tiles
run("Fuse dataset ...",
	"select=" + inputFilename + ".xml" +
	" process_angle=[All angles]" +
	" process_channel=[All channels]" +
	" process_illumination=[All illuminations]" +
	" process_tile=[All tiles]" +
	" process_timepoint=[All Timepoints]" +
	" bounding_box=[Currently Selected Views]" +
	" downsampling=1 pixel_type=[16-bit unsigned integer]" +
	" interpolation=[Linear Interpolation]" +
	" image=[Precompute Image]" +
	" interest_points_for_non_rigid=[-= Disable Non-Rigid =-]" +
	" blend preserve_original produce=[Each timepoint & channel]" +
	" fused_image=[Save as (compressed) TIFF stacks]" +
	" output_file_directory=" + fusePath +
	" filename_addition=" + filename);
