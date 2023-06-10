import os
import sys
import argparse
import pandas as pd
import numpy as np
import torch
import torch.utils.data
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim

##custom modules required
sys.path.append('../pytorch_model_helpers')
import pytorch_utils
import pytorch_helpers
from pytorch_utils import initialize_weights,SmoothBCEwLogits,TrainDataset,TestDataset
from pytorch_utils import train_fn,valid_fn,inference_fn,CNN_Model
from pytorch_helpers import drug_stratification,normalize,pca_features,model_eval_results
from pytorch_helpers import preprocess,split_data,check_if_shuffle_data,save_to_csv

class cp_1dcnn_moa_train_prediction:
    
    """
    This function performs 1D-CNN model training on the Cell painting level-4 profiles and also performs
    prediction on the hold-out test set. The model training includes running 5-Kfold cross validation on 
    the train data for the purpose of tuning the hyperparameters, and making prediction on the entire test 
    dataset for every fold and then averaging out the predictions to get the final test predictions.
    
    For more info:https://github.com/baosenguo/Kaggle-MoA-2nd-Place-Solution/blob/main/training/1d-cnn-train.ipynb
    
    Args:
            data_dir: directory that contains train, test and moa target labels
            (with their corresponding compounds) csv files.

            model_pred_dir: directory where model predictions for train & test data will be stored
            
            shuffle: True or False argument, to check if the train data is shuffled i.e. given to the wrong 
            target labels OR NOT
            
            Epochs: A number that defines the number of times that the 1D-CNN Model will be trained 
            on the entire training dataset.
            
            Batch_size: A number that defines number of samples to work through before updating the 
            internal model parameters. The number of training examples in one forward & backward pass.
            
            learning_rate: A number that controls how much we are adjusting the weights of our 1D-CNN network
            with respect the loss gradient after every pass/iteration. 
            
    Output:
            dataframes: train and hold-out test predictions are read in as csv files to the model_pred_dir
            saved cnn model: the 1D-CNN model for every train fold is saved in a model folder in the data_dir

    """
    
    def __init__(self, data_dir=None, model_pred_dir=None, shuffle=None, subsample=None, Epochs=None, Batch_size=None, learning_rate=None, file_indicator=None):

        self.data_dir = data_dir
        self.model_pred_dir = model_pred_dir
        self.shuffle = shuffle
        self.subsample = subsample
        if self.subsample:
            self.output_file_indicator = "_subsample"
        else:
            self.output_file_indicator = ""
        self.EPOCHS = Epochs
        self.BATCH_SIZE = Batch_size
        self.LEARNING_RATE = learning_rate
        self.file_indicator = file_indicator
    
    def cp_cnn_moa_train_prediction(self):
        
        print("Is GPU Available?")
        if torch.cuda.is_available():
            print("Yes, GPU is Available!!")
        else:
            print("No, GPU is NOT Available!!", "\n")
            
        DEVICE = ('cuda' if torch.cuda.is_available() else 'cpu')
        no_of_components = 25
        NFOLDS = 5
        WEIGHT_DECAY = 1e-5
        EARLY_STOPPING_STEPS = 10
        EARLY_STOP = False
        hidden_size=4096
        ##dir names
        model_file_name = "cp_1dcnn"
        model_dir_name = "cp_cnn_model"
        trn_pred_name = 'cp_train_pathway_preds_1dcnn'
        tst_pred_name = 'cp_test_pathway_preds_1dcnn'
        model_file_name,model_dir_name,trn_pred_name,tst_pred_name = \
        check_if_shuffle_data(self.shuffle, model_file_name, model_dir_name, trn_pred_name, tst_pred_name)
        model_dir = os.path.join(self.data_dir, model_dir_name)
        os.makedirs(model_dir, exist_ok=True)
        
        # Setup file names
        if self.shuffle:
            input_train_file = os.path.join(self.data_dir, f'train_shuffle_lvl4_data{self.file_indicator}.csv.gz')
            input_test_file = os.path.join(self.data_dir, f'test_shuffle_lvl4_data{self.file_indicator}.csv.gz')

        else:
            input_train_file = os.path.join(self.data_dir, f'train_lvl4_data{self.file_indicator}.csv.gz')
            input_test_file = os.path.join(self.data_dir, f'test_lvl4_data{self.file_indicator}.csv.gz')

        
        input_target_file = os.path.join(self.data_dir, f'target_labels{self.file_indicator}.csv')

        df_train = pd.read_csv(input_train_file, compression='gzip',low_memory = False)
        df_test = pd.read_csv(input_test_file, compression='gzip',low_memory = False)
        df_targets = pd.read_csv(input_target_file)
        
#         metadata_cols = ["Plate","Well","Treatment","Treatment_Clean","broad_sample","moa","pert_iname","Key"]
        metadata_cols = ["Plate","Well","Treatment","Treatment_Clean","moa","pert_iname","Key"]

        
        target_cols = df_targets.columns[1:]
        df_train_x, df_train_y, df_test_x, df_test_y = split_data(df_train, df_test, metadata_cols, target_cols)
        features = df_train_x.columns.tolist()
        num_features=len(features) + no_of_components
        num_targets=len(target_cols)
        df_train = drug_stratification(df_train,NFOLDS,target_cols,col_name='Key',cpd_freq_num=5)
        pos_weight = initialize_weights(df_train, target_cols, DEVICE)
        
        def model_train_pred(fold, Model = CNN_Model, df_train_y = df_train_y, df_test_y = df_test_y, features=features,
                             file_name = model_file_name):
            
            model_path = os.path.join(model_dir, file_name + f"_FOLD{fold}.pth")
            x_fold_train, y_fold_train, x_fold_val, y_fold_val, df_test_x_copy, val_idx = \
            preprocess(fold, df_train, df_train_x, df_train_y, df_test_x, no_of_components)
            train_dataset = TrainDataset(x_fold_train.values, y_fold_train.values)
            valid_dataset = TrainDataset(x_fold_val.values, y_fold_val.values)
            
            trainloader = torch.utils.data.DataLoader(train_dataset, batch_size=self.BATCH_SIZE, shuffle=True)
            validloader = torch.utils.data.DataLoader(valid_dataset, batch_size=self.BATCH_SIZE, shuffle=False)
            
            model = Model(num_features=num_features, num_targets=num_targets, hidden_size=hidden_size)
            model.to(DEVICE)
            optimizer = torch.optim.Adam(model.parameters(), lr=self.LEARNING_RATE, weight_decay=WEIGHT_DECAY, eps=1e-9)
            scheduler = optim.lr_scheduler.OneCycleLR(optimizer=optimizer, pct_start=0.1, div_factor=1e3,
                                                      max_lr=1e-2, epochs=self.EPOCHS, steps_per_epoch=len(trainloader))
            loss_train = SmoothBCEwLogits(smoothing = 0.001, pos_weight=pos_weight)
            loss_val = nn.BCEWithLogitsLoss()
            early_stopping_steps = EARLY_STOPPING_STEPS
            early_step = 0
            oof = np.zeros(df_train_y.shape)
            best_loss = np.inf
            best_loss_epoch = -1
            
            for epoch in range(self.EPOCHS):
                train_loss = train_fn(model, optimizer,scheduler, loss_train, trainloader, DEVICE)
                valid_loss, valid_preds = valid_fn(model, loss_val, validloader, DEVICE)
                if valid_loss < best_loss:
                    best_loss = valid_loss
                    best_loss_epoch = epoch
                    oof[val_idx] = valid_preds
                    torch.save(model.state_dict(), model_path)
                elif (EARLY_STOP == True):
                    early_step += 1
                    if (early_step >= early_stopping_steps):
                        break
                print(f"FOLD: {fold}, EPOCH: {epoch},train_loss: {train_loss:.6f},\
                valid_loss: {valid_loss:.6f} best_loss: {best_loss:.6f}, best_loss_epoch: {best_loss_epoch}")
                
            #--------------------- PREDICTION---------------------
            testdataset = TestDataset(df_test_x_copy.values)
            testloader = torch.utils.data.DataLoader(testdataset, batch_size=self.BATCH_SIZE, shuffle=False)
            model = Model(num_features=num_features, num_targets=num_targets, hidden_size=hidden_size)
            model.load_state_dict(torch.load(model_path))
            model.to(DEVICE)
            
            predictions = np.zeros(df_test_y.shape)
            predictions = inference_fn(model, testloader, DEVICE)
            return oof, predictions
        
        def run_k_fold(NFOLDS, df_train_y = df_train_y, df_test_y = df_test_y):
            oof = np.zeros(df_train_y.shape)
            predictions = np.zeros(df_test_y.shape)
            for fold in range(NFOLDS):
                oof_, pred_ = model_train_pred(fold)
                predictions += pred_ / NFOLDS
                oof += oof_
            return oof, predictions
        
        oofs_, predictions_ = run_k_fold(NFOLDS)
        df_oofs = pd.DataFrame(oofs_, columns=df_train_y.columns)
        df_preds = pd.DataFrame(predictions_, columns=df_test_y.columns)
        
        model_eval_results(df_train_y, oofs_, df_test_y, df_preds, target_cols)
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
    parser.add_argument('--subsample', action="store_true", help='Whether or not to use subsampled cell painting profiles to match L1000 count')
    ##model hyperparameters
    parser.add_argument('--batch_size', type=int, default = 256, nargs='?', help='Batch size for the model inputs')
    parser.add_argument('--learning_rate', type=float, default = 1e-3, nargs='?', help='learning rate')
    parser.add_argument('--epochs', type=int, default = 30, nargs='?', help='Number of epochs')
    parser.add_argument('--file_indicator', type=str, default = "",help='filename of the data indicating the model that was used, e.g. _vit_small, _vit_base etc.')
    return parser.parse_args()
    
if __name__ == '__main__':
    args = parse_args()
            
    cp_1dcnn = cp_1dcnn_moa_train_prediction(
        data_dir=args.data_dir,
        model_pred_dir=args.model_pred_dir,
        shuffle=args.shuffle,
        subsample=args.subsample,
        Epochs=args.epochs,
        Batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        file_indicator=args.file_indicator
    )
    
    cp_1dcnn.cp_cnn_moa_train_prediction()