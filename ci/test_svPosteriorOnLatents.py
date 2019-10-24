
import sys
import pdb
import os
import math
from scipy.io import loadmat
import numpy as np
import torch
from kernels import PeriodicKernel, ExponentialQuadraticKernel
from kernelMatricesStore import IndPointsLocsKMS, IndPointsLocsAndAllTimesKMS,\
                                IndPointsLocsAndAssocTimesKMS
from svPosteriorOnIndPoints import SVPosteriorOnIndPoints
from svPosteriorOnLatents import SVPosteriorOnLatentsAllTimes,\
                                 SVPosteriorOnLatentsAssocTimes

def test_computeMeansAndVars_allTimes():
    tol = 5e-6
    dataFilename = os.path.join(os.path.dirname(__file__), "data/Estep_Objective_PointProcess_svGPFA.mat")

    mat = loadmat(dataFilename)
    nLatents = mat["Z"].shape[0]
    nTrials = mat["Z"][0,0].shape[2]
    qMu0 = [torch.from_numpy(mat["q_mu"][(0,i)]).type(torch.DoubleTensor).permute(2,0,1) for i in range(nLatents)]
    qSVec0 = [torch.from_numpy(mat["q_sqrt"][(0,i)]).type(torch.DoubleTensor).permute(2,0,1) for i in range(nLatents)]
    qSDiag0 = [torch.from_numpy(mat["q_diag"][(0,i)]).type(torch.DoubleTensor).permute(2,0,1) for i in range(nLatents)]
    t = torch.from_numpy(mat["ttQuad"]).type(torch.DoubleTensor).permute(2, 0, 1)
    Z = [torch.from_numpy(mat["Z"][(i,0)]).type(torch.DoubleTensor).permute(2,0,1) for i in range(nLatents)]
    mu_k = torch.from_numpy(mat["mu_k_Quad"]).type(torch.DoubleTensor).permute(2,0,1)
    var_k = torch.from_numpy(mat["var_k_Quad"]).type(torch.DoubleTensor).permute(2,0,1)

    kernelNames = mat["kernelNames"]
    hprs = mat["hprs"]
    kernels = [[None] for k in range(nLatents)]
    for k in range(nLatents):
        if np.char.equal(kernelNames[0,k][0], "PeriodicKernel"):
            kernels[k] = PeriodicKernel(scale=1.0, lengthScale=float(hprs[k,0][0]), period=float(hprs[k,0][1]))
        elif np.char.equal(kernelNames[0,k][0], "rbfKernel"):
            kernels[k] = ExponentialQuadraticKernel(scale=1.0, lengthScale=float(hprs[k,0][0]))
        else:
            raise ValueError("Invalid kernel name: %s"%(kernelNames[k]))


    qU = SVPosteriorOnIndPoints()
    indPointsLocsKMS = IndPointsLocsKMS()
    indPointsLocsAndTimesKMS = IndPointsLocsAndAllTimesKMS()
    qK = SVPosteriorOnLatentsAllTimes(svPosteriorOnIndPoints=qU, 
                                      indPointsLocsKMS=indPointsLocsKMS, 
                                      indPointsLocsAndTimesKMS=
                                       indPointsLocsAndTimesKMS)

    params0 = {"qMu0": qMu0, "qSVec0": qSVec0, "qSDiag0": qSDiag0}
    qU.setInitialParams(initialParams=params0)

    indPointsLocsKMS.setKernels(kernels=kernels)
    indPointsLocsKMS.setIndPointsLocs(locs=Z)
    indPointsLocsKMS.buildKernelsMatrices()

    indPointsLocsAndTimesKMS.setKernels(kernels=kernels)
    indPointsLocsAndTimesKMS.setIndPointsLocs(locs=Z)
    indPointsLocsAndTimesKMS.setTimes(times=t)
    indPointsLocsAndTimesKMS.buildKernelsMatrices()

    qKMu, qKVar = qK.computeMeansAndVars()

    qKMuError = math.sqrt(((mu_k-qKMu)**2).mean())
    assert(qKMuError<tol)
    qKVarError = math.sqrt(((var_k-qKVar)**2).mean())
    assert(qKVarError<tol)

def test_computeMeansAndVars_assocTimes():
    tol = 5e-6
    dataFilename = os.path.join(os.path.dirname(__file__), "data/Estep_Objective_PointProcess_svGPFA.mat")

    mat = loadmat(dataFilename)
    nLatents = mat["Z"].shape[0]
    nTrials = mat["Z"][0,0].shape[2]
    qMu0 = [torch.from_numpy(mat["q_mu"][(0,i)]).type(torch.DoubleTensor).permute(2,0,1) for i in range(nLatents)]
    qSVec0 = [torch.from_numpy(mat["q_sqrt"][(0,i)]).type(torch.DoubleTensor).permute(2,0,1) for i in range(nLatents)]
    qSDiag0 = [torch.from_numpy(mat["q_diag"][(0,i)]).type(torch.DoubleTensor).permute(2,0,1) for i in range(nLatents)]
    Z = [torch.from_numpy(mat["Z"][(i,0)]).type(torch.DoubleTensor).permute(2,0,1) for i in range(nLatents)]
    Y = [torch.from_numpy(mat["Y"][tr,0]).type(torch.DoubleTensor) for tr in range(nTrials)]
    mu_k = [torch.from_numpy(mat["mu_k_Spikes"][0,tr]).type(torch.DoubleTensor) for tr in range(nTrials)]
    var_k = [torch.from_numpy(mat["var_k_Spikes"][0,tr]).type(torch.DoubleTensor) for tr in range(nTrials)]

    kernelNames = mat["kernelNames"]
    hprs = mat["hprs"]
    kernels = [[None] for k in range(nLatents)]
    for k in range(nLatents):
        if np.char.equal(kernelNames[0,k][0], "PeriodicKernel"):
            kernels[k] = PeriodicKernel(scale=1.0, lengthScale=float(hprs[k,0][0]), period=float(hprs[k,0][1]))
        elif np.char.equal(kernelNames[0,k][0], "rbfKernel"):
            kernels[k] = ExponentialQuadraticKernel(scale=1.0, lengthScale=float(hprs[k,0][0]))
        else:
            raise ValueError("Invalid kernel name: %s"%(kernelNames[k]))


    qU = SVPosteriorOnIndPoints()
    indPointsLocsKMS = IndPointsLocsKMS()
    indPointsLocsAndTimesKMS = IndPointsLocsAndAssocTimesKMS()
    qK = SVPosteriorOnLatentsAssocTimes(svPosteriorOnIndPoints=qU, 
                                        indPointsLocsKMS=indPointsLocsKMS, 
                                        indPointsLocsAndTimesKMS=
                                         indPointsLocsAndTimesKMS)

    params0 = {"qMu0": qMu0, "qSVec0": qSVec0, "qSDiag0": qSDiag0}
    qU.setInitialParams(initialParams=params0)

    indPointsLocsKMS.setKernels(kernels=kernels)
    indPointsLocsKMS.setIndPointsLocs(locs=Z)
    indPointsLocsKMS.buildKernelsMatrices()

    indPointsLocsAndTimesKMS.setKernels(kernels=kernels)
    indPointsLocsAndTimesKMS.setIndPointsLocs(locs=Z)
    indPointsLocsAndTimesKMS.setTimes(times=Y)
    indPointsLocsAndTimesKMS.buildKernelsMatrices()

    qKMu, qKVar = qK.computeMeansAndVars()

    for tr in range(nTrials):
        qKMuError = math.sqrt(((mu_k[tr]-qKMu[tr])**2).mean())
        assert(qKMuError<tol)
        qKVarError = math.sqrt(((var_k[tr]-qKVar[tr])**2).mean())
        assert(qKVarError<tol)

if __name__=="__main__":
    test_computeMeansAndVars_allTimes()
    test_computeMeansAndVars_assocTimes()
