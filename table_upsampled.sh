#!/bin/bash
python -m torch.distributed.launch --nproc_per_node=4 \
train_dense_encoder.py \
train="biencoder_local.yaml" \
train_datasets=[nq_train_table_only_upsampled] \
dev_datasets=[nq_dev_only_table] \
output_dir="/home1/deokhk_1/research/DPR/trained_model_checkpoint/upsample/table/"