from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import numpy as np
import tensorflow as tf
import pandas as pd
import argparse
import os
import time
import sys
import pwd
import pdb
import csv
import deepchem
import pickle
import dcCustom

def model_regression(
            train_dataset,
            valid_dataset,
            test_dataset,
            tasks,
            transformers,
            metric,
            model,
            prot_desc_dict,
            prot_desc_length,
            test=False,
            #hyper_parameters=None,
            seed=123,
            tensorboard = True,
            model_dir="./model_dir"):
  train_scores = {}
  valid_scores = {}
  test_scores = {}
  assert model in [
      'tf_regression', 'tf_regression_ft', 'rf_regression', 'graphconvreg',
      'dtnn', 'dag_regression', 'xgb_regression', 'weave_regression',
      'textcnn_regression', 'krr', 'ani', 'krr_ft', 'mpnn'
  ]
  model_name = model
  
  if model_name == 'weave_regression':
    # batch_size = hyper_parameters['batch_size']
    # nb_epoch = hyper_parameters['nb_epoch']
    # learning_rate = hyper_parameters['learning_rate']
    # n_graph_feat = hyper_parameters['n_graph_feat']
    # n_pair_feat = hyper_parameters['n_pair_feat']
    batch_size = 64
    learning_rate = 1e-3
    nb_epoch = 20

    model = dcCustom.models.WeaveTensorGraph(
      len(tasks),
      #n_atom_feat=n_features,
      #n_pair_feat=n_pair_feat,
      n_hidden=50,
      #n_graph_feat=n_graph_feat,
      batch_size=batch_size,
      learning_rate=learning_rate,
      use_queue=False,
      random_seed=seed,
      mode='regression',
      tensorboard = tensorboard,
      model_dir = model_dir,
      prot_desc_dict=prot_desc_dict,
      prot_desc_length=prot_desc_length)
  
  print('-----------------------------')
  print('Start fitting: %s' % model_name)
  if nb_epoch is None:
    model.fit(train_dataset)
  else:
    model.fit(train_dataset, nb_epoch=nb_epoch)

  train_scores[model_name] = model.evaluate(train_dataset, metric, transformers)
  valid_scores[model_name] = model.evaluate(valid_dataset, metric, transformers)
  if test:
    test_scores[model_name] = model.evaluate(test_dataset, metric, transformers)

  return train_scores, valid_scores, test_scores


def load_davis(featurizer = 'Weave', test=False, split='random', reload=True, K = 5):
  tasks = ['interaction_value']
  data_dir = "davis_data/"
  if reload:
    save_dir = os.path.join(data_dir, "tox21/" + featurizer + "/" + split)
    loaded, all_dataset, transformers = deepchem.utils.save.load_dataset_from_disk(
        save_dir)
    if loaded:
      return tasks, all_dataset, transformers
  
  dataset_file = os.path.join(data_dir, "restructured.csv")
  if featurizer == 'Weave':
    featurizer = deepchem.feat.WeaveFeaturizer()
  loader = dcCustom.data.CSVLoader(
      tasks = tasks, smiles_field="smiles", protein_field = "proteinName",
      featurizer=featurizer)
  dataset = loader.featurize(dataset_file, shard_size=8192)
  
  transformers = [
        deepchem.trans.NormalizationTransformer(
            transform_y=True, dataset=dataset)
  ]
  print("About to transform data")
  for transformer in transformers:
    dataset = transformer.transform(dataset)
    
  splitters = {
      'index': deepchem.splits.IndexSplitter(),
      'random': deepchem.splits.RandomSplitter(),
      'scaffold': deepchem.splits.ScaffoldSplitter(),
      'butina': deepchem.splits.ButinaSplitter(),
      'task': deepchem.splits.TaskSplitter()
  }
  splitter = splitters[split]
  if test:
    train, valid, test = splitter.train_valid_test_split(dataset)
    all_dataset = (train, valid, test)
    if reload:
      deepchem.utils.save.save_dataset_to_disk(save_dir, train, valid, test,
                                               transformers)
  else:
    fold_datasets = splitter.k_fold_split(dataset, K)
    all_dataset = fold_datasets
  
  return tasks, all_dataset, transformers
  # TODO: the implementation above could be prone to errors. Not entirely sure.

def load_prot_desc_dict(prot_desc_path):
  df = pd.read_csv(prot_desc_path, index_col=0)
  #protList = list(df.index)
  prot_desc_dict = {}
  for row in df.itertuples():
    descriptor = row[2:]
    descriptor = np.array(descriptor)
    descriptor = np.reshape(descriptor, (1, len(descriptor)))
    prot_desc_dict[row[0]] = descriptor    
  return prot_desc_dict

def run_analysis(dataset='davis', 
                 featurizer = 'Weave',
                 split= 'random',
                 out_path = '.',
                 fold_num = 5,
                 hyper_param_search = False, 
                 reload = True,
                 test = True, 
                 seed=123,
                 prot_desc_path="davis_data/prot_desc.csv"):
  metric = [deepchem.metrics.Metric(deepchem.metrics.rms_score)]

  print('-------------------------------------')
  print('Running on dataset: %s' % dataset)
  print('-------------------------------------')
  
  if test:
    tasks, all_dataset, transformers = load_davis(featurizer=featurizer, test=test,
                                                  split=split, reload=reload)
  else:
    tasks, all_dataset, transformers = load_davis(featurizer=featurizer, test=test,
                                                  reload=reload, K = fold_num)
  prot_desc_dict = load_prot_desc_dict(prot_desc_path)
  prot_desc_length = 8421
  
  # all_dataset will be a list of 5 elements (since we will use 5-fold cross validation),
  # each element is a tuple, in which the first entry is a training dataset, the second is
  # a validation dataset.

  time_start_fitting = time.time()
  train_scores_list = []
  valid_scores_list = []
  test_scores_list = []

  '''
  if hyper_param_search:
    if hyper_parameters is None:
      hyper_parameters = hps[model]
    search_mode = deepchem.hyper.GaussianProcessHyperparamOpt(model)
    hyper_param_opt, _ = search_mode.hyperparam_search(
        hyper_parameters,
        train_dataset,
        valid_dataset,
        transformers,
        metric,
        direction=direction,
        n_features=n_features,
        n_tasks=len(tasks),
        max_iter=max_iter,
        search_range=search_range)
    hyper_parameters = hyper_param_opt
  '''
  model = 'weave_regression'
  test_dataset = None
  if test:
    train_dataset, valid_dataset, test_dataset = all_dataset
    train_score, valid_score, test_score = model_regression(
          train_dataset,
          valid_dataset,
          test_dataset,
          tasks,
          transformers,
          metric,
          model,
          prot_desc_dict,
          prot_desc_length,
          #hyper_parameters=hyper_parameters,
          test = test,
          seed=seed)
    train_scores_list.append(train_score)
    valid_scores_list.append(valid_score)
    test_scores_list.append(test_score)
  else:
    for i in range(fold_num):
      train_score, valid_score, _ = model_regression(
          all_dataset[i][0],
          all_dataset[i][1],
          None,
          tasks,
          transformers,
          metric,
          model,
          prot_desc_dict,
          prot_desc_length,
          #hyper_parameters=hyper_parameters,
          test = test,
          seed=seed)

      train_scores_list.append(train_score)
      valid_scores_list.append(valid_score)

  time_finish_fitting = time.time()

  with open(os.path.join(out_path, 'results.csv'), 'a') as f:
    writer = csv.writer(f)
    model_name = list(train_scores_list[0].keys())[0]
    if test:
      train_score = train_scores_list[0]
      valid_score = valid_scores_list[0]
      test_score = test_scores_list[0]
      for i in train_score[model_name]:
        output_line = [
                  dataset,
                  model_name, i, 'train',
                  train_score[model_name][i], 'valid', valid_score[model_name][i]
        ]
        output_line.extend(['test', test_score[model_name][i]])
        writer.writerow(output_line)
    else:
      for h in range(fold_num):
        train_score = train_scores_list[h]
        valid_score = valid_scores_list[h]
        for i in train_score[model_name]:
          output_line = [
                dataset,
                model_name, i, 'train',
                train_score[model_name][i], 'valid', valid_score[model_name][i]
          ]          
          output_line.extend(
              ['time_for_running', time_finish_fitting - time_start_fitting])
          writer.writerow(output_line)
  #if hyper_param_search:
  #  with open(os.path.join(out_path, dataset + model + '.pkl'), 'w') as f:
  #    pickle.dump(hyper_parameters, f)
  
if __name__ == '__main__':
  run_analysis()


