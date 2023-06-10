import os
import sys
import time
import datetime
import argparse
import pandas as pd
import numpy as np
from iterstrat.ml_stratifiers import MultilabelStratifiedKFold
from skmultilearn.adapt import MLkNN

##custom modules required
from mlknn_helpers import mlknn_train_pred,model_eval_results, save_to_csv
from mlknn_helpers import split_data, check_if_shuffle_data

class cp_mlknn_moa_train_prediction:
    
    """
    This function performs Multilabel-KNearest Neighbours training on Cell painting level-4 profiles and also performs 
    prediction on the hold-out test set. The model training includes running 5-Kfold cross validation on the train data 
    for the purpose of tuning the hyperparameters (searching for the best "K"), and making prediction on the entire test 
    dataset for every fold and then averaging out the predictions to get the final test predictions.
    
    Args:
            data_dir: directory that contains train, test and moa target labels
            (with their corresponding compounds) csv files.

            model_pred_dir: directory where model predictions for train & test data will be stored
            
            shuffle: True or False argument, to check if the train data is shuffled i.e. given to the wrong 
            target labels OR NOT
            
            k_list: A list of "K" nearest neighbours to perform gridsearch on.
            
    Output:
            dataframes: train and hold-out test predictions are read in as csv files to the model_pred_dir

    """
    
    def __init__(self, data_dir=None, model_pred_dir=None, shuffle=None, subsample=None, k_list=None, file_indicator=None):

        self.data_dir = data_dir
        self.model_pred_dir = model_pred_dir
        self.shuffle = shuffle
        self.subsample = subsample
        if self.subsample:
            self.output_file_indicator = "_subsample"
        else:
            self.output_file_indicator = ""
        self.file_indicator = file_indicator
        self.k_list = k_list
    
    def cp_mlknn_moa_train_pred(self):
            
        NFOLDS = 5
        ##dir names
        model_file_name = None
        model_dir_name = None
        trn_pred_name = 'cp_train_preds_mlknn'
        tst_pred_name = 'cp_test_preds_mlknn'
        _,_,trn_pred_name,tst_pred_name = check_if_shuffle_data(
            self.shuffle,
            model_file_name, 
            model_dir_name,
            trn_pred_name,
            tst_pred_name
        )
        
        # Setup file names
        if self.shuffle:
            input_train_file = os.path.join(self.data_dir, f'train_shuffle_lvl4_data{self.file_indicator}.csv.gz')
            input_test_file = os.path.join(self.data_dir, f'test_shuffle_lvl4_data{self.file_indicator}.csv.gz')

        else:
            input_train_file = os.path.join(self.data_dir, f'train_lvl4_data{self.file_indicator}.csv.gz')
            input_test_file = os.path.join(self.data_dir, f'test_lvl4_data{self.file_indicator}.csv.gz')

        
        input_target_file = os.path.join(self.data_dir, f'target_labels{self.file_indicator}.csv')

        # if self.shuffle:
        #     if self.subsample:
        #         input_train_file = os.path.join(self.data_dir, "train_shuffle_lvl4_data_subsample.csv.gz")
        #         input_test_file = os.path.join(self.data_dir, "test_lvl4_data_subsample.csv.gz")
        #     else:
        #         input_train_file = os.path.join(self.data_dir, "train_shuffle_lvl4_data_targets.csv.gz")
        #         input_test_file = os.path.join(self.data_dir, "test_lvl4_data_targets.csv.gz")
        # else:
        #     if self.subsample:
        #         input_train_file = os.path.join(self.data_dir, "train_lvl4_data_subsample.csv.gz")
        #         input_test_file = os.path.join(self.data_dir, "test_lvl4_data_subsample.csv.gz")
        #     else:
        #         input_train_file = os.path.join(self.data_dir, "train_lvl4_data_targets_pathways.csv.gz")
        #         input_test_file = os.path.join(self.data_dir, "test_lvl4_data_targets_pathways.csv.gz")
        
        # if self.subsample:
        #     input_target_file = os.path.join(self.data_dir, 'target_labels_subsample.csv')
        # else:
        #     input_target_file = os.path.join(self.data_dir, 'target_labels_targets_pathways.csv')

        df_train = pd.read_csv(input_train_file, compression='gzip',low_memory = False)
        df_test = pd.read_csv(input_test_file, compression='gzip',low_memory = False)
        df_targets = pd.read_csv(input_target_file)
        
#         metadata_cols = ["Plate","Well","Treatment","Treatment_Clean","broad_sample","moa","pert_iname","Key"]
        metadata_cols = ["Plate","Well","Treatment","Treatment_Clean","moa","pert_iname","Key"]

        target_cols = df_targets.columns[1:]
        df_train_x, df_train_y, df_test_x, df_test_y = split_data(df_train, df_test, metadata_cols, target_cols)
        df_oofs,df_preds = mlknn_train_pred(self.k_list, df_train_x, df_train_y, df_test_x, df_test_y, target_cols, 
                                            NFOLDS = NFOLDS)
        
        model_eval_results(df_train_y, df_oofs.values, df_test_y, df_preds, target_cols)
        save_to_csv(df_preds, self.model_pred_dir, f"{tst_pred_name}{self.output_file_indicator}.csv")
        save_to_csv(df_oofs, self.model_pred_dir, f"{trn_pred_name}{self.output_file_indicator}.csv.gz", compress="gzip")
        print("\n All is set, Train and Test predictions have been read as csv files into the model predictions directory!!")
    
def parse_args():
    """Arguments to pass to this Script"""
    
    parser = argparse.ArgumentParser(description="Parse arguments")
    ##file directories
    parser.add_argument('--data_dir', type=str, help='directory that contains train, test and target labels csv files')
    parser.add_argument('--model_pred_dir', type=str, help='directory where model predictions for train & test will be stored')
    parser.add_argument('--shuffle', action="store_true", help='True or False argument, to check if the train data is shuffled \
    i.e. given to the wrong target labels OR NOT')
    parser.add_argument('--file_indicator', type=str, default = "",help='filename of the data indicating the model that was used, e.g. _vit_small, _vit_base etc.')
    parser.add_argument('--subsample', action="store_true", help='Whether or not to use subsampled cell painting profiles to match L1000 count')
    ##model hyperparameters
    parser.add_argument('--k_list', type=list, default = [9], nargs='?', help='A list of "K" nearest neighbours to\
    perform gridsearch on')
    return parser.parse_args()
    
if __name__ == '__main__':
    args = parse_args()

    cp_mlknn = cp_mlknn_moa_train_prediction(
        data_dir=args.data_dir,
        model_pred_dir=args.model_pred_dir,
        shuffle=args.shuffle,
        subsample=args.subsample,
        k_list=args.k_list,
        file_indicator = args.file_indicator
    )
    cp_mlknn.cp_mlknn_moa_train_pred()