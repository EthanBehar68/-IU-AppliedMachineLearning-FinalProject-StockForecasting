import sys
from test import *
from model import Model
from fastquant import get_stock_data
from hmmlearn import hmm
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import math
import time
from multiprocessing import Pool


class GHMM(Model):
    def __init__(self,params):
        super().__init__(params)
        self.n_components = params['n_components']
        self.algorithm = params['algorithm']
        self.n_iter = params['n_iter']
        self.d = params['d']
    
    def train(self, train_data):
        self.train_obs = self.data_prep(train_data)
        self.model = hmm.GaussianHMM(n_components=self.n_components,
                                     algorithm=self.algorithm,
                                     n_iter=self.n_iter)

        self.model.fit(self.train_obs)
    
    def predict(self,test_data):        
        test_close_prices = test_data['close'].values
        test_open_prices = test_data['open'].values

        # use a latency of d days. So observations start as training data
        observed = self.train_obs.iloc[-self.d:].values
        
        # list to hold predictions
        preds = []
        
        # loop through all points we want to test
        for i in range(len(test_data)):
            # try 50x10x10 possible values for O_d+1
            change = np.arange(-0.2,0.2,0.4/6000)

            observations = [np.array([c]) for c in change]
            
            # compute all log likelihoods w/ their observations in parallel
            jump = int(len(observations)/20)
            with Pool(processes=20) as pool:
                results = pool.starmap(self.log_lik_calc, [(observed, observations[i:i+jump]) for i in range(0,len(observations),jump)])

            best = {'obs':None, 'log_lik':-math.inf}
            for log_liks in results:
                for obs,log_lik in log_liks:
                    if log_lik > best['log_lik']:
                        best['obs'],best['log_lik'] = obs,log_lik

            # actually stack the best day on to the observations to use for next test point
            # drop the first thing in observed to shift our latency window `d`
            observed = np.vstack((observed,best['obs']))
            observed = observed[1:]

            #calculate the close value from best
            pred_close = best['obs'][0]*test_open_prices[i]+test_open_prices[i]
            preds.append(pred_close)

            print(f'{i+1}/{len(test_data)}',end='\r',flush=True)
        print('DONE')
        return preds,test_close_prices
    
    def log_lik_calc(self, observed, observations):
        log_liks = []
        for o in observations:
            obs = np.vstack((observed,o))
            log_lik = self.model.score(obs)
            log_liks.append((o,log_lik))

        return log_liks
    
    def data_prep(self, data):
        df = pd.DataFrame(data=None, columns=['fracChange'])
        df['fracChange'] = (data['close']-data['open'])/data['open']

        return df


if __name__ == "__main__":
    params = {'n_components': 3, 
              'algorithm': 'map', 
              'n_iter': 100, 
              'd': 5,
              'name':'GHMM3'}
    
    print('testing best found parameters paper tests')
    test = Test(Model=GHMM, params=params, tests=paper_tests, f='ghmm3-paper-tests.json', plot=False)
    test.run_tests()

    print('testing best found parameters own tests')
    test = Test(Model=GHMM, params=params, tests=own_tests, f='ghmm3-own-tests.json', plot=False)
    test.run_tests()