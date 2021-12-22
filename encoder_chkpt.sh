#!/bin/bash
python -m torch.distributed.launch --nproc_per_node=4 \
train_dense_encoder.py \
train="biencoder_chkpt" \
train_datasets=[nq_train_with_table_fin] \
dev_datasets=[nq_dev_with_table_fin] \
train="biencoder_chkpt" \
model_file="/home/deokhk/research/MultiQA/model/DPR/dpr/data/downloads/checkpoint/retriever/single-adv-hn/nq/bert-base-encoder.cp" \
output_dir="/home/deokhk/research/DPR/output_dir/chkpt/"
