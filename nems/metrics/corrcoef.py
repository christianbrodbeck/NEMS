# -*- coding: utf-8 -*-
import numpy as np
import scipy.special

import logging
log = logging.getLogger(__name__)

import nems.epoch as ep


def corrcoef(result, pred_name='pred', resp_name='resp'):
    '''
    Given the evaluated data, return the mean squared error

    Parameters
    ----------
    result : A Recording object
        Generally the output of `model.evaluate(phi, data)`
    pred_name : string
        Name of prediction in the result recording
    resp_name : string
        Name of response in the result recording

    Returns
    -------
    cc : float
        Correlation coefficient between the prediction and response.

    Example
    -------
    >>> result = model.evaluate(data, phi)
    >>> cc = corrcoef(result, 'pred', 'resp')

    Note
    ----
    This function is written to be compatible with both numeric (i.e., Numpy)
    and symbolic (i.e., Theano, TensorFlow) computation. Please do not edit
    unless you know what you're doing. (@bburan TODO: Is this still true?)
    '''
    pred = result[pred_name].as_continuous()
    resp = result[resp_name].as_continuous()
    if pred.shape[0] > 1:
        raise ValueError("multi-channel signals not supported yet.")
        
    ff = np.isfinite(pred) & np.isfinite(resp)
    if np.sum(ff) == 0:
        return 0
    else:
        cc = np.corrcoef(pred[ff], resp[ff])
        return cc[0, 1]


def r_floor(result, pred_name='pred', resp_name='resp'):
    '''
    corr coef floor based on shuffled responses
    '''
    # if running validation test, also measure r_floor
    X1 = result[pred_name].as_continuous()
    X2 = result[resp_name].as_continuous()
    
    if X1.shape[0] > 1:
        raise ValueError("multi-channel signals not supported yet.")
    
    # remove all nans from pred and resp
    ff = np.isfinite(X1) & np.isfinite(X2)
    X1=X1[ff]
    X2=X2[ff]
    
    # figure out how many samples to use in each shuffle
    if len(X1)>500:
        n=500
    else:
        n=len(X1)
        
    # compute cc for 1000 shuffles
    rf = np.zeros([1000, 1])
    for rr in range(0, len(rf)):
        n1 = (np.random.rand(n) * len(X1)).astype(int)
        n2 = (np.random.rand(n) * len(X2)).astype(int)
        rf[rr] = np.corrcoef(X1[n1], X2[n2])[0, 1]
        
    rf = np.sort(rf[np.isfinite(rf)], 0)
    if len(rf):
        r_floor = rf[np.int(len(rf) * 0.95)]
    else:
        r_floor = 0
        
    return r_floor


def _r_single(X, N=100):
    """
    Assume X is trials X time raster
    
    test data from SPN recording
    X=rec['resp'].extract_epoch('STIM_BNB+si464+si1889')
    """
    
    if X.shape[1] > 1:
        raise ValueError("multi-channel signals not supported yet.")
    
    repcount=X.shape[0]
    if repcount <= 1:
        log.info('repcount<=1, rnorm=0')
        return 0

    paircount=np.int(scipy.special.comb(repcount, 2))
    pairs = []
    for p1 in range(repcount):
        for p2 in range (p1+1, repcount):
            pairs.append([p1,p2])
        
    if paircount < N:
        N = paircount
            
    if N == 1:
        # only two repeats, break up data in time to get a better
        # estimate of single-trial correlations
        raise ValueError("2 repeats condition not supported yet.")
        # N=10;
        # bstep=size(pred,1)./N;
        # rac=zeros(N,1);
        # for nn=1:N,
        #     tt=round((nn-1).*bstep+1):round(nn*bstep);
        #     if ~isempty(tt) && std(resp(tt,1))>0 && std(resp(tt,2))>0,
        #         rac(nn)=xcov(resp(tt,1),resp(tt,2),0,'coeff');
        #     end
        # end
    
    else:
    
        rac=np.zeros(N)
        sidx = np.argsort(np.random.rand(paircount))
        for nn in range(N):
            X1 = X[pairs[sidx[nn]][0],0,:]
            X2 = X[pairs[sidx[nn]][1],0,:]
            
            # remove all nans from pred and resp
            ff = np.isfinite(X1) & np.isfinite(X2)
            X1=X1[ff]
            X2=X2[ff]
            
            rac[nn] = np.corrcoef(X1, X2)[0, 1]

    rac=np.mean(rac);
    if rac<0.05:
        rac = 0.05
    
    return rac


def r_ceiling(result, fullrec, pred_name='pred', resp_name='resp', N=100):
    """
    Assume X is trials X time raster
    
    test data from SPN recording
    X=rec['resp'].extract_epoch('STIM_BNB+si464+si1889')
    """
    epoch_regex = '^STIM_'
    epochs_to_extract = ep.epoch_names_matching(result[pred_name].epochs, epoch_regex)
    folded_pred = result[pred_name].extract_epochs(epochs_to_extract)
    
    rnorm_c = 0
    n = 0
    resp = fullrec[resp_name].rasterize()
    
    for k, d in folded_pred.items():
        if np.sum(np.isfinite(d)) > 0:
            
            X = resp.extract_epoch(k)            
            rac = _r_single(X, N)

            # print(k)
            # print(rac)
            
            if rac > 0:    
                repcount = X.shape[0]
                rs = np.zeros(repcount)
                for nn in range(repcount):
                    X1 = X[nn,0,:]
                    X2 = d[0,0,:]
                    
                    # remove all nans from pred and resp
                    ff = np.isfinite(X1) & np.isfinite(X2)
                    X1=X1[ff]
                    X2=X2[ff]
                    
                    rs[nn] = np.corrcoef(X1, X2)[0, 1]
                    
                rs=np.mean(rs)
                
                rnorm_c += (rs / np.sqrt(rac)) * X1.shape[-1]
                n += X1.shape[-1]
                
    # weighted average based on number of samples in each epoch
    rnorm = rnorm_c / n
    
    return rnorm
                
    
