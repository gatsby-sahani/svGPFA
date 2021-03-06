
import pdb
import sys
import os
import random
import torch
import plotly
import matplotlib.pyplot as plt
import pickle
import configparser
import pandas as pd
sys.path.append("../src")
import simulations.svGPFA.simulations
import stats.gaussianProcesses.eval
from utils.svGPFA.configUtils import getKernels, getLatentsMeansFuncs, getLinearEmbeddingParams
from utils.svGPFA.miscUtils import getLatentsSamples, getTrialsTimes
import plot.svGPFA.plotUtils
from stats.pointProcess.tests import KSTestTimeRescalingNumericalCorrection

def getLatentsMeansAndSTDs(meansFuncs, kernels, trialsTimes):
    nTrials = len(kernels)
    nLatents = len(kernels[0])
    latentsMeans = [[] for r in range(nTrials)]
    latentsSTDs = [[] for r in range(nTrials)]

    for r in range(nTrials):
        latentsMeans[r] = torch.empty((nLatents, len(trialsTimes[r])))
        latentsSTDs[r] = torch.empty((nLatents, len(trialsTimes[r])))
        for k in range(nLatents):
            gp = stats.gaussianProcesses.eval.GaussianProcess(mean=meansFuncs[r][k], kernel=kernels[r][k])
            latentsMeans[r][k,:] = gp.mean(t=trialsTimes[r])
            latentsSTDs[r][k,:] = gp.std(t=trialsTimes[r])
    return latentsMeans, latentsSTDs

def getLatentsTimes(trialsLengths, dt):
    nTrials = len(trialsLengths)
    latentsTimes = [[] for r in range(nTrials)]
    for r in range(nTrials):
        latentsTimes[r] = torch.linspace(0, trialsLengths[r], round(trialsLengths[i]/dt))
    return latentsTimes

def main(argv):
    if len(argv)!=2:
        print("Usage {:s} <simulation config number>".format(argv[0]))
        return
    trialKSTestTimeRescaling = 0
    neuronKSTestTimeRescaling = 0
    trialCIFToPlot = 0
    neuronCIFToPlot = 0
    dtCIF = 1e-3
    gamma = 10

    # load data and initial values
    simConfigNumber = int(argv[1])
    simConfigFilename = "data/{:08d}_simulation_metaData.ini".format(simConfigNumber)
    simConfig = configparser.ConfigParser()
    simConfig.read(simConfigFilename)
    nLatents = int(simConfig["control_variables"]["nLatents"])
    nNeurons = int(simConfig["control_variables"]["nNeurons"])
    trialsLengths = [float(str) for str in simConfig["control_variables"]["trialsLengths"][1:-1].split(",")]
    nTrials = len(trialsLengths)
    T = torch.tensor(trialsLengths).max()
    dtSimulate = float(simConfig["control_variables"]["dt"])
    dtLatentsFig = 1e-1
    gpRegularization = 1e-3

    randomPrefixUsed = True
    while randomPrefixUsed:
        simNumber = random.randint(0, 10**8)
        metaDataFilename = \
            "results/{:08d}_simulation_metaData.ini".format(simNumber)
        if not os.path.exists(metaDataFilename):
           randomPrefixUsed = False
    simResFilename = "results/{:08d}_simRes.pickle".format(simNumber)
    latentsFigFilename = \
        "figures/{:08d}_simulation_latents.png".format(simNumber)
    cifFigFilename = \
        "figures/{:08d}_simulation_cif_trial{:03d}_neuron{:03d}.png".format(simNumber, trialCIFToPlot, neuronCIFToPlot)
    spikesTimesFigFilename = \
        "figures/{:08d}_simulation_spikesTimes.png".format(simNumber)
    ksTestTimeRescalingFigFilename = \
        "figures/{:08d}_simulation_ksTestTimeRescaling.png".format(simNumber)
    rocFigFilename = "figures/{:08d}_simulation_rocAnalisis_trial{:03d}_neuron{:03d}.png".format(estResNumber, trialToAnalyze, neuronToAnalyze)

    with torch.no_grad():
        kernels = getKernels(nLatents=nLatents, nTrials=nTrials, config=simConfig)
        latentsMeansFuncs = getLatentsMeansFuncs(nLatents=nLatents, nTrials=nTrials, config=simConfig)
        trialsTimes = getTrialsTimes(trialsLengths=trialsLengths, dt=dtSimulate)
        print("Computing latents samples")
        C, d = getLinearEmbeddingParams(nNeurons=nNeurons, nLatents=nLatents, config=simConfig)
        latentsSamples = getLatentsSamples(meansFuncs=latentsMeansFuncs,
                                           kernels=kernels,
                                           trialsTimes=trialsTimes,
                                           gpRegularization=gpRegularization,
                                           dtype=C.dtype)

        simulator = simulations.svGPFA.simulations.GPFASimulator()
        res = simulator.simulate(trialsTimes=trialsTimes, latentsSamples=latentsSamples, C=C, d=d, linkFunction=torch.exp)
        spikesTimes = res["spikesTimes"]
        cifTimes = res["cifTimes"]
        cifValues = res["cifValues"]
        latentsMeans, latentsSTDs = getLatentsMeansAndSTDs(meansFuncs=latentsMeansFuncs, kernels=kernels, trialsTimes=trialsTimes)

    simRes = {"times": trialsTimes, 
              "latents": latentsSamples,
              "latentsMeans": latentsMeans, 
              "latentsSTDs": latentsSTDs,
              "cifTimes": cifTimes, 
              "cifValues": cifValues,
              "spikes": spikesTimes}
    with open(simResFilename, "wb") as f: pickle.dump(simRes, f)

    simResConfig = configparser.ConfigParser()
    simResConfig["simulation_params"] = {"simInitConfigFilename": simConfigFilename}
    simResConfig["simulation_results"] = {"simResFilename": simResFilename}
    with open(metaDataFilename, "w") as f:
        simResConfig.write(f)

    pLatents = plot.svGPFA.plotUtils.getSimulatedLatentsPlot(trialsTimes=trialsTimes, latentsSamples=latentsSamples, latentsMeans=latentsMeans, latentsSTDs=latentsSTDs, figFilename=latentsFigFilename)
    # pLatents = ggplotly(pLatents)
    # pLatents.show()

    timesCIFToPlot = cifTimes[trialCIFToPlot]
    valuesCIFToPlot = cifValues[trialCIFToPlot][neuronCIFToPlot]
    title = "Trial {:d}, Neuron {:d}".format(trialCIFToPlot, neuronCIFToPlot)
    plot.svGPFA.plotUtils.plotCIF(times=timesCIFToPlot, values=valuesCIFToPlot, title=title, figFilename=cifFigFilename)

    pSpikes = plot.svGPFA.plotUtils.getSimulatedSpikeTimesPlot(spikesTimes=spikesTimes, figFilename=spikesTimesFigFilename)
    # pSpikes = ggplotly(pSpikes)
    # pSpikes.show()

    T = torch.tensor(trialsLengths).max()
    oneTrialCIFTimes = torch.arange(0, T, dtCIF)
    cifTimes = torch.unsqueeze(torch.ger(torch.ones(nTrials), oneTrialCIFTimes), dim=2)
    cifTimesKS = cifTimes[trialKSTestTimeRescaling,:,0]
    cifValuesKS = cifValues[trialKSTestTimeRescaling][neuronKSTestTimeRescaling]
    spikesTimesKS = spikesTimes[trialKSTestTimeRescaling][neuronKSTestTimeRescaling]
    diffECDFsX, diffECDFsY, estECDFx, estECDFy, simECDFx, simECDFy, cb = KSTestTimeRescalingNumericalCorrection(spikesTimes=spikesTimesKS, cifTimes=cifTimesKS, cifValues=cifValuesKS, gamma=gamma)
    title = "Trial {:d}, Neuron {:d} ({:d} spikes)".format(trialKSTestTimeRescaling, neuronKSTestTimeRescaling, len(spikesTimesKS))
    plot.svGPFA.plotUtils.plotResKSTestTimeRescalingNumericalCorrection(diffECDFsX=diffECDFsX, diffECDFsY=diffECDFsY, estECDFx=estECDFx, estECDFy=estECDFy, simECDFx=simECDFx, simECDFy=simECDFy, cb=cb, figFilename=ksTestTimeRescalingFigFilename, title=title)

    pk = cifValuesKS*dtCIF
    bins = pd.interval_range(start=0, end=T, periods=len(pk))
    # start binning spikes using pandas
    cutRes, _ = pd.cut(spikesTimesKS, bins=bins, retbins=True)
    Y = torch.from_numpy(cutRes.value_counts().values)

    fpr, tpr, thresholds = metrics.roc_curve(Y, pk, pos_label=1)
    roc_auc = metrics.auc(fpr, tpr)
    plot.svGPFA.plotUtils.plotResROCAnalysis(fpr=fpr, tpr=tpr, auc=roc_auc, figFilename=rocFigFilename)

    plt.show()

    pdb.set_trace()

if __name__=="__main__":
    main(sys.argv)
