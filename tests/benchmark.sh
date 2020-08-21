# Small test
time ../workflows/download_test_data.sh small_test small_data
mkdir small_test_results
time python ../workflows/preprocessing_pipeline.py small_test_config.toml 0
rm -rf small_data
rm -rf small_test_results

