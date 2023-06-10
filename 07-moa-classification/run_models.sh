q#!/bin/bash

# Run bash script to train models and predict compound mechanism of action
# For each type of features
#     1. Using CellProfiler features
#     2. Using DINO features
#     3. Using CNN features

cp_data_dir="../../2.data_split/model_data/cp/"

model_pred_dir_cellpro="../../Final_cellprofiler_v3/"
file_indicator_cellpro="_cellprofiler_final"

model_pred_dir_dino="../../Final_dino_v3/"
file_indicator_dino="_dino_final"

model_pred_dir_cnn="../../Final_cnn_v3/"
file_indicator_cnn="_CNN_final"

cd ..
cd 3.moa_prediction_models_new/resnet_models_moa_prediction

python cp_resnet_train_pred.py --data_dir $cp_data_dir --feat_type "cellprofiler" --model_pred_dir $model_pred_dir_cellpro --file_indicator $file_indicator_cellpro

python cp_resnet_train_pred.py --data_dir $cp_data_dir --feat_type "cellprofiler" --model_pred_dir $model_pred_dir_cellpro --shuffle --file_indicator $file_indicator_cellpro

python cp_resnet_train_pred.py --data_dir $cp_data_dir --feat_type "dino" --model_pred_dir $model_pred_dir_dino --file_indicator $file_indicator_dino

python cp_resnet_train_pred.py --data_dir $cp_data_dir --feat_type "dino" --model_pred_dir $model_pred_dir_dino --shuffle --file_indicator $file_indicator_dino

python cp_resnet_train_pred.py --data_dir $cp_data_dir --feat_type "cnn" --model_pred_dir $model_pred_dir_cnn --file_indicator $file_indicator_cnn

python cp_resnet_train_pred.py --data_dir $cp_data_dir --feat_type "cnn" --model_pred_dir $model_pred_dir_cnn --shuffle --file_indicator $file_indicator_cnn
