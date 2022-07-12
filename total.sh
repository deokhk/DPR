#!/bin/bash
python -m torch.distributed.launch --nproc_per_node=4 \
train_dense_encoder.py \
train="biencoder_scratch.yaml" \
train_datasets=[nq_train_with_table] \
dev_datasets=[nq_dev_with_table] \
output_dir="/home/deokhk/research/DPR/output_dir/total/"