import numpy as np
from scipy.spatial.distance import correlation
from pathlib import Path
import pickle

    
def get_direct_gene_labels(rounds):
    """
    """
    direct_genes = []
    for round_index, imaging_round in enumerate(rounds, start=1):
        channels = imaging_round["channels"]
        composite_channel_indices = imaging_round.get("composite_channels", [])

        for channel_index, channel in enumerate(channels):
            if channel_index not in composite_channel_indices:
                direct_genes.append(channel)

    direct_genes.sort()

    return direct_genes

def analyze_decompression_all_samples(config, parallelize=0):
    """
    """
    # TODO: write docstring

    workspace_directory = config["workspace_directory"]
    training_directory = Path(config["training_directory"])
    segmentation_directory = Path(workspace_directory, "segmented")
    decompression_directory = Path(workspace_directory, "decompressed")
    output_directory = Path(workspace_directory, "analysis")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    if parallelize > 0:
        num_processes = mp.cpu_count()
        processes = []
        for sample in samples:
            process = mp.Process(target=analyze_decompression_single_sample, args=(sample, segmentation_directory, decompression_directory, output_directory, training_directory))
            process.start()
            processes.append(process)

        for process in processes:
            process.join()
    else:
        for sample in samples:
            analyze_decompression_single_sample(sample, segmentation_directory, decompression_directory, output_directory, training_directory)

def analyze_decompression_single_sample(sample, segmentation_directory, decompression_directory, output_directory, training_directory):
    """
    """

    sample_name = sample["name"]
    sample_segmentation_subdirectory = segmentation_directory / sample_name
    sample_decompression_subdirectory = decompression_directory / sample_name
    sample_output_subdirectory = output_directory / sample_name
    sample_output_subdirectory.mkdir(exist_ok=True)

    direct_measurements_filepath = sample_segmentation_subdirectory / "direct_measurements.npy"
    direct_measurements = np.load(direct_measurements_filepath)
    decompressed_measurements_filepath = sample_decompression_subdirectory / "decompressed_measurements.npy"
    decompressed_measurements = np.load(decompressed_measurements_filepath)

    all_gene_labels_filepath = training_directory / "gene_labels.npy"
    all_gene_labels = np.load(all_gene_labels_filepath)

    rounds = sample["rounds"]
    direct_gene_labels = get_direct_gene_labels(rounds)

    direct_gene_indices = np.in1d(all_gene_labels, direct_gene_labels)
    decompressed_direct_measurements = decompressed_measurements[direct_gene_indices]
    print(decompressed_measurements.shape)
    print(decompressed_direct_measurements.shape)
    print(direct_measurements.shape)
    overall_correlation = 1 - correlation(direct_measurements.flatten(), decompressed_direct_measurements.flatten())

    
    print(overall_correlation)
    results = {"overall_correlation": overall_correlation }
    with open(sample_output_subdirectory / "results.pkl", "wb") as result_file:
        pickle.dump(results, result_file)
