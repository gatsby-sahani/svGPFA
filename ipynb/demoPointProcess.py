
import sys
import os
import pdb
import math
import random
import torch
import pickle
import configparser
import pandas as pd
import statsmodels.tsa.stattools
import sklearn.metrics
sys.path.append(os.path.expanduser("../src"))
sys.path.append(os.path.expanduser("../scripts"))
import demoUtils
import stats.svGPFA.svGPFAModelFactory
import stats.svGPFA.svEM
import plot.svGPFA.plotUtils
import utils.svGPFA.configUtils
import stats.pointProcess.tests
import utils.svGPFA.miscUtils

def main(argv):
    simResNumber = 96784468
    estInitNumber = 5
    trialToPlot = 0
    neuronToPlot = 18
    dtCIF = 1e-3
    gamma = 10

    # load data and initial values
    simResConfigFilename = "../scripts/results/{:08d}_simulation_metaData.ini".format(simResNumber)
    simResConfig = configparser.ConfigParser()
    simResConfig.read(simResConfigFilename)
    simInitConfigFilename = simResConfig["simulation_params"]["simInitConfigFilename"]
    simInitConfigFilename = "../scripts/" + simInitConfigFilename
    simResFilename = simResConfig["simulation_results"]["simResFilename"]
    simResFilename = "../scripts/" + simResFilename

    simInitConfig = configparser.ConfigParser()
    simInitConfig.read(simInitConfigFilename)
    nLatents = int(simInitConfig["control_variables"]["nLatents"])
    nNeurons = int(simInitConfig["control_variables"]["nNeurons"])
    trialsLengths = [float(str) for str in simInitConfig["control_variables"]["trialsLengths"][1:-1].split(",")]
    dtSimulate = float(simInitConfig["control_variables"]["dt"])
    nTrials = len(trialsLengths)

    with open(simResFilename, "rb") as f: simRes = pickle.load(f)
    spikesTimes = simRes["spikes"]
    trueLatents = simRes["latents"]
    simCIFsValues = simRes["cifValues"]
    trueLatents = [trueLatents[r][:nLatents,:] for r in range(nTrials)]
    trueLatentsMeans = simRes["latentsMeans"]
    trueLatentsSTDs = simRes["latentsSTDs"]
    trueLatentsSTDs = [trueLatentsSTDs[r][:nLatents,:] for r in range(nTrials)]
    timesTrueValues = torch.linspace(0, torch.max(torch.tensor(trialsLengths)), trueLatents[0].shape[1])

    estInitConfigFilename = "../scripts/data/{:08d}_estimation_metaData.ini".format(estInitNumber)
    estInitConfig = configparser.ConfigParser()
    estInitConfig.read(estInitConfigFilename)
    nIndPointsPerLatent = [int(str) for str in estInitConfig["control_variables"]["nIndPointsPerLatent"][1:-1].split(",")]
    nIndPointsPerLatent = nIndPointsPerLatent[:nLatents]
    nTestPoints = int(estInitConfig["control_variables"]["nTestPoints"])
    firstIndPoint = float(estInitConfig["control_variables"]["firstIndPoint"])
    initCondEmbeddingSTD = float(estInitConfig["control_variables"]["initCondEmbeddingSTD"])
    initCondIndPointsScale = float(estInitConfig["control_variables"]["initCondIndPointsScale"])
    kernelsParams0NoiseSTD = float(estInitConfig["control_variables"]["kernelsParams0NoiseSTD"])
    indPointsLocsKMSRegEpsilon = float(estInitConfig["control_variables"]["indPointsLocsKMSRegEpsilon"])
    nQuad = int(estInitConfig["control_variables"]["nQuad"])

    optimParamsConfig = estInitConfig._sections["optim_params"]
    optimParams = {}
    optimParams["emMaxNIter"] = int(optimParamsConfig["emMaxNIter".lower()])
    #
    optimParams["eStepEstimate"] = optimParamsConfig["eStepEstimate".lower()]=="True"
    optimParams["eStepMaxNIter"] = int(optimParamsConfig["eStepMaxNIter".lower()])
    optimParams["eStepTol"] = float(optimParamsConfig["eStepTol".lower()])
    optimParams["eStepLR"] = float(optimParamsConfig["eStepLR".lower()])
    optimParams["eStepLineSearchFn"] = optimParamsConfig["eStepLineSearchFn".lower()]
    optimParams["eStepNIterDisplay"] = int(optimParamsConfig["eStepNIterDisplay".lower()])
    #
    optimParams["mStepModelParamsEstimate"] = optimParamsConfig["mStepModelParamsEstimate".lower()]=="True"
    optimParams["mStepModelParamsMaxNIter"] = int(optimParamsConfig["mStepModelParamsMaxNIter".lower()])
    optimParams["mStepModelParamsTol"] = float(optimParamsConfig["mStepModelParamsTol".lower()])
    optimParams["mStepModelParamsLR"] = float(optimParamsConfig["mStepModelParamsLR".lower()])
    optimParams["mStepModelParamsLineSearchFn"] = optimParamsConfig["mStepModelParamsLineSearchFn".lower()]
    optimParams["mStepModelParamsNIterDisplay"] = int(optimParamsConfig["mStepModelParamsNIterDisplay".lower()])
    #
    optimParams["mStepKernelParamsEstimate"] = optimParamsConfig["mStepKernelParamsEstimate".lower()]=="True"
    optimParams["mStepKernelParamsMaxNIter"] = int(optimParamsConfig["mStepKernelParamsMaxNIter".lower()])
    optimParams["mStepKernelParamsTol"] = float(optimParamsConfig["mStepKernelParamsTol".lower()])
    optimParams["mStepKernelParamsLR"] = float(optimParamsConfig["mStepKernelParamsLR".lower()])
    optimParams["mStepKernelParamsLineSearchFn"] = optimParamsConfig["mStepKernelParamsLineSearchFn".lower()]
    optimParams["mStepKernelParamsNIterDisplay"] = int(optimParamsConfig["mStepKernelParamsNIterDisplay".lower()])
    #
    optimParams["mStepIndPointsEstimate"] = optimParamsConfig["mStepIndPointsEstimate".lower()]="True"
    optimParams["mStepIndPointsMaxNIter"] = int(optimParamsConfig["mStepIndPointsMaxNIter".lower()])
    optimParams["mStepIndPointsTol"] = float(optimParamsConfig["mStepIndPointsTol".lower()])
    optimParams["mStepIndPointsLR"] = float(optimParamsConfig["mStepIndPointsLR".lower()])
    optimParams["mStepIndPointsLineSearchFn"] = optimParamsConfig["mStepIndPointsLineSearchFn".lower()]
    optimParams["mStepIndPointsNIterDisplay"] = int(optimParamsConfig["mStepIndPointsNIterDisplay".lower()])
    #
    optimParams["verbose"] = optimParamsConfig["verbose"]=="True"

    testTimes = torch.linspace(0, torch.max(torch.tensor(spikesTimes[0][0])), nTestPoints)

    CFilename = "../scripts/" + simInitConfig["embedding_params"]["C_filename"]
    dFilename = "../scripts/" + simInitConfig["embedding_params"]["d_filename"]
    C, d = utils.svGPFA.configUtils.getLinearEmbeddingParams(nNeurons=nNeurons, nLatents=nLatents, CFilename=CFilename, dFilename=dFilename)
    C0 = C + torch.randn(C.shape)*initCondEmbeddingSTD
    C0 = C0[:,:nLatents]
    d0 = d + torch.randn(d.shape)*initCondEmbeddingSTD

    legQuadPoints, legQuadWeights = demoUtils.getLegQuadPointsAndWeights(nQuad=nQuad, trialsLengths=trialsLengths)

    kernels = utils.svGPFA.configUtils.getKernels(nLatents=nLatents, nTrials=nTrials, config=simInitConfig)
    kernelsParams0 = demoUtils.getKernelsParams0(kernels=kernels, noiseSTD=kernelsParams0NoiseSTD)
    kernels = kernels[0] # the current code uses the same kernels for all trials
    kernelsParams0 = kernelsParams0[0] # the current code uses the same kernels for all trials

    qMu0, qSVec0, qSDiag0 = demoUtils.getSVPosteriorOnIndPointsParams0(nIndPointsPerLatent=nIndPointsPerLatent, nLatents=nLatents, nTrials=nTrials, scale=initCondIndPointsScale)

    Z0 = demoUtils.getIndPointLocs0(nIndPointsPerLatent=nIndPointsPerLatent,
                          trialsLengths=trialsLengths, firstIndPoint=firstIndPoint)

    qUParams0 = {"qMu0": qMu0, "qSVec0": qSVec0, "qSDiag0": qSDiag0}
    qHParams0 = {"C0": C0, "d0": d0}
    kmsParams0 = {"kernelsParams0": kernelsParams0,
                  "inducingPointsLocs0": Z0}
    initialParams = {"svPosteriorOnIndPoints": qUParams0,
                     "kernelsMatricesStore": kmsParams0,
                     "svEmbedding": qHParams0}
    quadParams = {"legQuadPoints": legQuadPoints,
                  "legQuadWeights": legQuadWeights}

    # create model
    model = stats.svGPFA.svGPFAModelFactory.SVGPFAModelFactory.buildModel(
        conditionalDist=stats.svGPFA.svGPFAModelFactory.PointProcess,
        linkFunction=stats.svGPFA.svGPFAModelFactory.ExponentialLink,
        embeddingType=stats.svGPFA.svGPFAModelFactory.LinearEmbedding,
        kernels=kernels,
        indPointsLocsKMSEpsilon=indPointsLocsKMSRegEpsilon)

    # maximize lower bound
    svEM = stats.svGPFA.svEM.SVEM()
    lowerBoundHist, elapsedTimeHist  = svEM.maximize(
        model=model, measurements=spikesTimes, initialParams=initialParams,
        quadParams=quadParams, optimParams=optimParams,
        plotLatentsEstimates=False)

    # plot lower bound history
    plot.svGPFA.plotUtils.plotLowerBoundHist(lowerBoundHist=lowerBoundHist)

    # plot true and estimated latents
    testMuK, testVarK = model.predictLatents(newTimes=testTimes)
    indPointsLocs = model.getIndPointsLocs()
    plot.svGPFA.plotUtils.plotTrueAndEstimatedLatents(timesEstimatedValues=testTimes, muK=testMuK, varK=testVarK, indPointsLocs=indPointsLocs, timesTrueValues=timesTrueValues, trueLatents=trueLatents, trueLatentsMeans=trueLatentsMeans, trueLatentsSTDs=trueLatentsSTDs, trialToPlot=trialToPlot)

    # plot model params
    tLatentsMeansFuncs = utils.svGPFA.configUtils.getLatentsMeansFuncs(nLatents=nLatents, nTrials=nTrials, config=simInitConfig)
    trialsTimes = utils.svGPFA.miscUtils.getTrialsTimes(trialsLengths=trialsLengths, dt=dtSimulate)
    tLatentsMeans = utils.svGPFA.miscUtils.getLatentsMeanFuncsSamples(latentsMeansFuncs=tLatentsMeansFuncs, trialsTimes=trialsTimes, dtype=C.dtype)
    kernelsParams = model.getKernelsParams()
    with torch.no_grad(): latentsMeans, _ = model.predictLatents(newTimes=trialsTimes[0])
    with torch.no_grad(): estimatedC, estimatedD = model.getSVEmbeddingParams()

    plot.svGPFA.plotUtils.plotTrueAndEstimatedKernelsParams(trueKernels=kernels, estimatedKernelsParams=kernelsParams)

    plot.svGPFA.plotUtils.plotTrueAndEstimatedLatentsMeans(trueLatentsMeans=tLatentsMeans, estimatedLatentsMeans=latentsMeans, trialsTimes=trialsTimes)

    plot.svGPFA.plotUtils.plotTrueAndEstimatedEmbeddingParams(trueC=C, trueD=d, estimatedC=estimatedC, estimatedD=estimatedD)

    title = "Trial {:d}, Neuron {:d}".format(trialToPlot, neuronToPlot)
    # CIF
    T = torch.tensor(trialsLengths).max().item()
    oneTrialCIFTimes = torch.arange(0, T, dtCIF)
    cifTimes = torch.unsqueeze(torch.ger(torch.ones(nTrials), oneTrialCIFTimes), dim=2)
    with torch.no_grad(): cifValues = model.computeMeanCIFs(times=cifTimes)
    plot.svGPFA.plotUtils.plotSimulatedAndEstimatedCIFs(times=cifTimes[trialToPlot, :, 0], simCIFValues=simCIFsValues[trialToPlot][neuronToPlot], estCIFValues=cifValues[trialToPlot][neuronToPlot], title=title)

    # KS test time rescaling with numerical correction
    spikesTimesKS = spikesTimes[trialToPlot][neuronToPlot]
    cifTimesKS = cifTimes[trialToPlot,:,0]
    cifValuesKS = cifValues[trialToPlot][neuronToPlot]

    title = "Trial {:d}, Neuron {:d} ({:d} spikes)".format(trialToPlot, neuronToPlot, len(spikesTimesKS))

    diffECDFsX, diffECDFsY, estECDFx, estECDFy, simECDFx, simECDFy, cb = stats.pointProcess.tests.KSTestTimeRescalingNumericalCorrection(spikesTimes=spikesTimesKS, cifTimes=cifTimesKS, cifValues=cifValuesKS, gamma=gamma)
    plot.svGPFA.plotUtils.plotResKSTestTimeRescalingNumericalCorrection(diffECDFsX=diffECDFsX, diffECDFsY=diffECDFsY, estECDFx=estECDFx, estECDFy=estECDFy, simECDFx=simECDFx, simECDFy=simECDFy, cb=cb, title=title)

    # KS test time rescaling with analytical correction
    t0 = math.floor(cifTimesKS.min())
    tf = math.ceil(cifTimesKS.max())
    dt = (cifTimesKS[1]-cifTimesKS[0]).item()
    utSRISIs, uCDF, cb, utRISIs = stats.pointProcess.tests.KSTestTimeRescalingAnalyticalCorrectionUnbinned(spikesTimes=spikesTimesKS, cifValues=cifValuesKS, t0=t0, tf=tf, dt=dt)
    sUTRISIs, _ = torch.sort(utSRISIs)

    plot.svGPFA.plotUtils.plotResKSTestTimeRescalingAnalyticalCorrection(sUTRISIs=sUTRISIs, uCDF=uCDF, cb=cb, title=title)

    plot.svGPFA.plotUtils.plotDifferenceCDFs(sUTRISIs=sUTRISIs, uCDF=uCDF, cb=cb)

    plot.svGPFA.plotUtils.plotScatter1Lag(x=utRISIs, title=title)

    acfRes, confint = statsmodels.tsa.stattools.acf(x=utRISIs, unbiased=True, alpha=0.05)
    plot.svGPFA.plotUtils.plotACF(acf=acfRes, Fs=1/dt, confint=confint, title=title)

    # ROC predictive analysis
    pk = cifValuesKS*dtCIF
    bins = pd.interval_range(start=0, end=T, periods=len(pk))
    cutRes, _ = pd.cut(spikesTimesKS, bins=bins, retbins=True)
    Y = torch.from_numpy(cutRes.value_counts().values)
    fpr, tpr, thresholds = sklearn.metrics.roc_curve(Y, pk, pos_label=1)
    roc_auc = sklearn.metrics.auc(fpr, tpr)
    plot.svGPFA.plotUtils.plotResROCAnalysis(fpr=fpr, tpr=tpr, auc=roc_auc, title=title)

    pdb.set_trace()

if __name__ == "__main__":
    main(sys.argv)
