import numpy as np
import spams
import pandas as pd
import scipy.spatial as sp, scipy.cluster.hierarchy as hc
import matplotlib
from scipy.spatial.distance import squareform

from pathlib import Path

matplotlib.use('Agg')
import matplotlib.pyplot as plt
matplotlib.style.use('ggplot')
#import seaborn as sns
from scipy.spatial import distance
from scipy.stats import entropy

def select_and_correct_comeasured(x,xc,phi,phi_corr,training_corr,phi_thresh=0.6,train_thresh=0.1):
    # find comeasured genes that are not coexpressed
    comeasured = []
    for i in range(phi_corr.shape[0]):
        xs = np.argsort(-phi_corr[i])
        for j in xs:
            if phi_corr[i,j] < phi_thresh:
                break
            comeasured.append((phi_corr[i,j],i,j))
    corrected_pairs = []
    for c in sorted(comeasured,reverse=True):
        if training_corr[c[1],c[2]] < train_thresh:
            x, both_nz = correct_coexpression(x,xc,phi,c[1],c[2])
            corrected_pairs.append((c[1],c[2], both_nz))
    return x, corrected_pairs

def correct_coexpression(x,xc,phi,i,j):
    # pick the gene with nearest expression pattern in scRNA
    thresh_i = np.percentile(x[i],99.9)/100
    thresh_j = np.percentile(x[j],99.9)/100
    both_nz = (x[i] > thresh_i)*(x[j] > thresh_j)
    dist = distance.cdist([phi[:,i], phi[:,j]], xc[:,both_nz].T,'correlation')
    i_closer = np.where(both_nz)[0][dist[0] < dist[1]]
    j_closer = np.where(both_nz)[0][dist[0] > dist[1]]
    x[i, j_closer] = 0
    x[j, i_closer] = 0
    return x, both_nz

def decompress_measurements_all_samples(config, parallelize=0):
    """
    """
    # TODO: write docstring

    workspace_directory = config["workspace_directory"]
    training_directory = Path(config["training_directory"])
    input_directory = Path(workspace_directory, "segmented")
    output_directory = Path(workspace_directory, "decompressed")
    output_directory.mkdir(exist_ok=True)

    samples = config["samples"]

    # TODO: Figure out if it's possible to parallelize by sample here.
    if parallelize > 0:
        num_processes = mp.cpu_count()
        processes = []
        for sample in samples:
            process = mp.Process(target=decompress_measurements_single_sample, args=(sample, input_directory, output_directory, training_directory))
            process.start()
            processes.append(process)

        for process in processes:
            process.join()
    else:
        for sample in samples:
            decompress_measurements_single_sample(sample, input_directory, output_directory, training_directory)

def decompress_measurements_single_sample(sample, input_directory, output_directory, training_directory):
    """
    """

    sample_name = sample["name"]
    sample_input_subdirectory = input_directory / sample_name
    sample_output_subdirectory = output_directory / sample_name
    sample_output_subdirectory.mkdir(exist_ok=True)

    phi = np.load(training_directory / "phi.npy")    
    num_measurements, num_genes = phi.shape
    
    gene_correlations = squareform(np.load(training_directory / "correlations.npy"))   
    gene_modules = np.load(training_directory / "gene_modules.npy")

    num_measurements_per_gene = phi.sum(axis=0)
    # TODO: question about this: why do we subtract the np.eye after and not before normalizing?
    phi_correlations = ((phi.T @ phi)/num_measurements_per_gene).T - np.eye(num_genes)

    composite_measurements_filepath = sample_input_subdirectory / "composite_measurements.npy"
    composite_measurements = np.load(composite_measurements_filepath)

    analysis_operator = phi.dot(gene_modules).astype(np.float32)
    synthesis_coefficients = sparse_decode(composite_measurements, analysis_operator, lasso_scaling_factor = 0.1, method='lasso')

    decompressed_measurements = gene_modules.dot(synthesis_coefficients)
    # TODO: below we have some "correction" due to the nature of our genomic data. Can we get rid of these edits?
    decompressed_measurements[np.isnan(decompressed_measurements)] = 0
    decompressed_measurements[decompressed_measurements < 0] = 0

    # TODO: figure out what corrected measurements are
    # if args.correct_comeasured:
    #   np.save('%s/ReconstructedImages/%s/%s/segmented.segmentation.npy' % (args.basepath, tissue, args.method), xhat)
    #   xhat,cp = select_and_correct_comeasured(xhat,composite_measurements,phi,phi_corr,train_corr)
    #   np.save('%s/ReconstructedImages/%s/%s/segmented.segmentation.adjusted.npy' % (args.basepath, tissue, args.method), xhat)
    # X1.append(xhat)

    print(sample_output_subdirectory / "decompressed_measurements.npy")
    
    np.save(sample_output_subdirectory / "decompressed_measurements.npy", decompressed_measurements)


def sparse_decode(analysis_coefficients, analysis_operator, lasso_scaling_factor=0.1, ridge_sparsity=None, minimum_loss=1., minimum_ridge_sparsity=0, method='omp'):
    """
    """
    print(analysis_coefficients.shape)
    print(analysis_operator.shape)
    analysis_coefficients_fortran = np.asfortranarray(analysis_coefficients)
    analysis_operator_fortran = np.asfortranarray(analysis_operator)
    coefficient_norm = np.linalg.norm(analysis_coefficients)

    num_bases, dimensionality = analysis_coefficients.shape
    _, latent_dimensionality = analysis_operator.shape
    if method == 'omp':
        if not ridge_sparsity:
            ridge_sparsity = min(num_bases, latent_dimensionality)  
        while ridge_sparsity < minimum_ridge_sparsity:
            sparse_synthesis_coefficients = spams.omp(analysis_coefficients_fortran, analysis_operator_fortran,
                          L=ridge_sparsity, numThreads=4)
            synthesis_coefficients = np.asarray(sparse_synthesis_coefficients.todense())
            loss = 1 - np.linalg.norm(analysis_coefficients - analysis_operator.dot(W))**2/coefficient_norm**2
            if loss < minimium_loss:
                break
            k -= 1
    elif method == 'lasso':
        print("Using lasso")
        lasso_penalty = lasso_scaling_factor * coefficient_norm**2 / dimensionality
        print("Lasso penalty is ", lasso_penalty)
        # TODO: set numThreads to some reasonable amount based on mp.cpu_count() and parallelization level
        sparse_synthesis_coefficients = spams.lasso(analysis_coefficients_fortran, analysis_operator_fortran,
                        lambda1=lasso_penalty, mode=1, numThreads=4, pos=False)
        synthesis_coefficients = np.asarray(sparse_synthesis_coefficients.todense())

    print(synthesis_coefficients.sum())

    return synthesis_coefficients

def get_sorted_direct_genes(rounds, input_directory):
    """
    """
    direct_genes = []
    for round_index, imaging_round in enumerate(rounds, start=1):
        round_directory = ("round%d" % round_index)
        round_input_subdirectory = input_directory / round_directory

        channels = imaging_round["channels"]
        composite_channel_indices = imaging_round.get("composite_channels", [])

        for channel_index, channel in enumerate(channels):
            if channel_index not in composite_channel_indices:
                direct_genes.append(channel)

    direct_genes.sort()

    return direct_genes

#if __name__ == '__main__':
#    AllGenes = np.load('%s/labels.genes.npy' % args.trainpath)
#    tissue = 'tissue%s' % t
#    composite_measurements = np.load('%s/FilteredCompositeImages/%s/%s/composite_measurements.npy' % (args.basepath, tissue,args.method))
#    direct_measurements = np.load('%s/FilteredCompositeImages/%s/%s/direct_measurements.npy' % (args.basepath, tissue,args.method))
#    direct_labels = np.load('%s/FilteredCompositeImages/%s/%s/direct_labels.npy' % (args.basepath, tissue, args.method))
#    W = sparse_decode(composite_measurements,phi.dot(U).astype(np.float32),0.1,method='lasso')
#    xhat = U.dot(W)
#    xhat[np.isnan(xhat)] = 0
#    xhat[xhat < 0] = 0
#
#    idx = [np.where(AllGenes == l)[0][0] for l in direct_labels]
#    xhat = xhat[idx]
#    n = direct_measurements.shape[0]+1
#    fig, axes = plt.subplots(max(2,int(np.floor(np.sqrt(n)))), int(np.ceil(np.sqrt(n))))
#    axes = axes.flatten()
#    plt.rcParams["axes.labelsize"] = 3
#    for i in range(n-1):
#        corr = 1-distance.correlation(direct_measurements[i],xhat[i])
#        sns_plt = sns.scatterplot(direct_measurements[i],xhat[i],ax=axes[i])
#        _= sns_plt.set(xlabel='Direct Intensity (arb. units)',ylabel='Recovered Intensity (arb. units)',title='%s; r=%.4f' % (direct_labels[i],corr))
#        print(tissue,direct_labels[i],corr)
#        C.append(corr)
#    corr = 1-distance.correlation(direct_measurements.flatten(),xhat.flatten())
#    sns_plt = sns.scatterplot(direct_measurements.flatten(),xhat.flatten(),ax=axes[-1])
#    _= sns_plt.set(xlabel='Direct Intensity (arb. units)',ylabel='Recovered Intensity (arb. units)',title='%s; r=%.4f' % ('all points',corr))
#    print(tissue,'all points',corr)
#
#    # _=plt.tight_layout()
#    # if args.correct_comeasured:
#    #   outpath = '%s/ReconstructedImages/%s/%s/scatter.segmented.heuristic_correction.png' % (args.basepath, tissue, args.method)
#    # else:
#    #   outpath = '%s/ReconstructedImages/%s/%s/scatter.segmented.png' % (args.basepath, tissue, args.method)
#    # fig.savefig(outpath)
#    # plt.close()
#
#    X0.append(direct_measurements.flatten())
#    X2.append(xhat.flatten())
#
#    X0 = np.hstack(X0)
#    X1 = np.hstack(X1)
#    X2 = np.hstack(X2)
#    corr = 1-distance.correlation(X0,X2)
#    sns_plt = sns.scatterplot(X0,X2)
#    _= sns_plt.set(xlabel='Direct Intensity (arb. units)',ylabel='Recovered Intensity (arb. units)',title='%s; r=%.4f' % ('all tissues, all points',corr))
#    print('all tissues, all points',corr)
#    print('average gene corr', np.average(C))
#    fig = sns_plt.get_figure()
#    if args.correct_comeasured:
#        outpath = '%s/ReconstructedImages/scatter.segmented.heuristic_correction.png' % (args.basepath)
#    else:
#        outpath = '%s/ReconstructedImages/scatter.segmented.png' % (args.basepath)
#    fig.savefig(outpath)
#    plt.close()
#    # gene-gene correlation
#    Corr = 1-distance.squareform(distance.pdist(X1,'correlation')) - np.eye(X1.shape[0])
#    df = pd.DataFrame(Corr,columns=AllGenes,index=AllGenes)
#    linkage = hc.linkage(distance.squareform(1-Corr-np.eye(X1.shape[0])), method='average')
#    sns_plt = sns.clustermap(df,mask=(df == 0), row_linkage=linkage, col_linkage=linkage)
#    sns_plt.savefig('%s/ReconstructedImages/gene_similarity.segmented.png' % args.basepath)
#    plt.close()
#    avg_ng = np.average([np.exp(entropy(x)) for x in X1.T if x.sum()>0])
#    print('average genes / cell:',avg_ng)
#
#
#    
