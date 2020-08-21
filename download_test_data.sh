TEST_NAME=$1
DATA_DIRECTORY=$2

gsutil cp -r gs://fc-5de89d3c-1dab-43ba-81fc-7c15266efb43/data/$TEST_NAME $DATA_DIRECTORY
