
import pdb
import torch
import time
# from .utils import clock

class SVEM:

    # @clock
    def maximize(self, model, measurements, initialParams, quadParams, optimParams):
        defaultOptimParams = {"emMaxNIter":20,
                              "eStepMaxNIter":100,
                              "eStepTol":1e-3,
                              "eStepLR":1e-0,
                              "eStepLineSearchFn":"strong_wolfe", 
                              "eStepNIterDisplay":1,
                              "mStepModelParamsMaxNIter":100,
                              "mStepModelParamsTol":1e-3,
                              "mStepModelParamsLR":1e-0,
                              "mStepModelParamsLineSearchFn":"strong_wolfe", 
                              "mStepModelParamsNIterDisplay":1,
                              "mStepKernelParamsMaxNIter":100,
                              "mStepKernelParamsTol":1e-3,
                              "mStepKernelParamsLR":1e-3,
                              "mStepKernelParamsLineSearchFn":"strong_wolfe", 
                              "mStepKernelParamsNIterDisplay":1,
                              "mStepIndPointsMaxNIter":100,
                              "mStepIndPointsTol":1e-3,
                              "mStepIndPointsLR":1e-0,
                              "mStepIndPointsLineSearchFn":"strong_wolfe", 
                              "mStepIndPointsNIterDisplay":1,
                              "verbose":True}
        optimParams = {**defaultOptimParams, **optimParams}
        model.setMeasurements(measurements=measurements)
        model.setInitialParams(initialParams=initialParams)
        model.setQuadParams(quadParams=quadParams)
        model.buildKernelsMatrices()

        iter = 0
        lowerBoundHist = []
        elapsedTimeHist = []
        startTime = time.time()
        while iter<optimParams["emMaxNIter"]:
            print("Iteration %02d, E-Step start"%(iter))
            maxRes = self._eStep(
                model=model,
                maxNIter=optimParams["eStepMaxNIter"],
                tol=optimParams["eStepTol"],
                lr=optimParams["eStepLR"],
                lineSearchFn=optimParams["eStepLineSearchFn"],
                verbose=optimParams["verbose"],
                nIterDisplay=optimParams["eStepNIterDisplay"])
            print("Iteration %02d, E-Step end: %f"%(iter, -maxRes['lowerBound']))
            print("Iteration %02d, M-Step Model Params start"%(iter))
            # pdb.set_trace()
            maxRes = self._mStepModelParams(
                model=model,
                maxNIter=optimParams["mStepModelParamsMaxNIter"],
                tol=optimParams["mStepModelParamsTol"],
                lr=optimParams["mStepModelParamsLR"],
                lineSearchFn=optimParams["mStepModelParamsLineSearchFn"],
                verbose=optimParams["verbose"],
                nIterDisplay=optimParams["mStepModelParamsNIterDisplay"])
            print("Iteration %02d, M-Step Model Params end: %f"%
                    (iter, -maxRes['lowerBound']))
            print("Iteration %02d, M-Step Kernel Params start"%(iter))
            # pdb.set_trace()
            maxRes = self._mStepKernelParams(
                model=model,
                maxNIter=optimParams["mStepKernelParamsMaxNIter"],
                tol=optimParams["mStepKernelParamsTol"],
                lr=optimParams["mStepKernelParamsLR"],
                lineSearchFn=optimParams["mStepKernelParamsLineSearchFn"],
                verbose=optimParams["verbose"],
                nIterDisplay=optimParams["mStepKernelParamsNIterDisplay"])
            print("Iteration %02d, M-Step Kernel Params end: %f"%
                    (iter, -maxRes['lowerBound']))
            print("Iteration %02d, M-Step Ind Points start"%(iter))
            # pdb.set_trace()
            maxRes = self._mStepIndPoints(
                model=model,
                maxNIter=optimParams["mStepIndPointsMaxNIter"],
                tol=optimParams["mStepIndPointsTol"],
                lr=optimParams["mStepIndPointsLR"],
                lineSearchFn=optimParams["mStepIndPointsLineSearchFn"],
                verbose=optimParams["verbose"],
                nIterDisplay=optimParams["mStepIndPointsNIterDisplay"])
            print("Iteration %02d, M-Step Ind Points end: %f"%
                    (iter, -maxRes['lowerBound']))
            elapsedTimeHist.append(time.time()-startTime)
            iter += 1
            lowerBoundHist.append(maxRes['lowerBound'])
            # pdb.set_trace()
        return lowerBoundHist, elapsedTimeHist

    def _eStep(self, model, maxNIter, tol, lr, lineSearchFn, verbose, nIterDisplay):
        x = model.getSVPosteriorOnIndPointsParams()
        evalFunc = model.eval
        optimizer = torch.optim.LBFGS(x, lr=lr, line_search_fn=lineSearchFn)
        # optimizer = torch.optim.Adam(x, lr=lr)
        answer= self._setupAndMaximizeStep(x=x, evalFunc=evalFunc, optimizer=optimizer, maxNIter=maxNIter, tol=tol, verbose=verbose, nIterDisplay=nIterDisplay)
        return answer

    def _mStepModelParams(self, model, maxNIter, tol, lr, lineSearchFn, verbose, nIterDisplay):
        x = model.getSVEmbeddingParams()
        svPosteriorOnLatentsStats = model.computeSVPosteriorOnLatentsStats()
        evalFunc = lambda: \
            model.evalELLSumAcrossTrialsAndNeurons(
                svPosteriorOnLatentsStats=svPosteriorOnLatentsStats)
        displayFmt = "Step: %d, negative sum of expected log likelihood: %f"
        optimizer = torch.optim.LBFGS(x, lr=lr, line_search_fn=lineSearchFn)
        # pdb.set_trace()
        # optimizer = torch.optim.Adam(x, lr=lr)
        answer = self._setupAndMaximizeStep(x=x, evalFunc=evalFunc, optimizer=optimizer, maxNIter=maxNIter, tol=tol, verbose=verbose, nIterDisplay=nIterDisplay, displayFmt=displayFmt)
        return answer

    def _mStepKernelParams(self, model, maxNIter, tol, lr, lineSearchFn, verbose, nIterDisplay):
        x = model.getKernelsParams()
        def evalFunc():
            model.buildKernelsMatrices()
            answer = model.eval()
            return answer
        # optimizer = torch.optim.Adam(x, lr=lr)
        optimizer = torch.optim.LBFGS(x, lr=lr, line_search_fn=lineSearchFn)
        answer = self._setupAndMaximizeStep(x=x, evalFunc=evalFunc, optimizer=optimizer, maxNIter=maxNIter, tol=tol, verbose=verbose, nIterDisplay=nIterDisplay)
        return answer

    def _mStepIndPoints(self, model, maxNIter, tol, lr, lineSearchFn, verbose, nIterDisplay):
        x = model.getIndPointsLocs()
        def evalFunc():
            model.buildKernelsMatrices()
            answer = model.eval()
            return answer
        optimizer = torch.optim.LBFGS(x, lr=lr, line_search_fn=lineSearchFn)
        # optimizer = torch.optim.Adam(x, lr=lr)
        answer = self._setupAndMaximizeStep(x=x, evalFunc=evalFunc, optimizer=optimizer, maxNIter=maxNIter, tol=tol, verbose=verbose, nIterDisplay=nIterDisplay)
        return answer

    def _setupAndMaximizeStep(self, x, evalFunc, optimizer, maxNIter, tol, verbose, nIterDisplay, displayFmt="Step: %d, negative lower bound: %f"):
        for i in range(len(x)):
            x[i].requires_grad = True
        maxRes = self._maximizeStep(evalFunc=evalFunc, optimizer=optimizer, maxNIter=maxNIter, tol=tol, verbose=verbose, nIterDisplay=nIterDisplay, displayFmt=displayFmt)
        for i in range(len(x)):
            x[i].requires_grad = False
        return maxRes

    def _maximizeStep(self, evalFunc, optimizer, maxNIter, tol, verbose, nIterDisplay, displayFmt="Step: %d, negative lower bound: %f"):
        iterCount = 0
        lowerBoundHist = []
        curEval = torch.tensor([float("inf")])
        converged = False
        while not converged and iterCount<maxNIter:
            def closure():
                # details on this closure at http://sagecal.sourceforge.net/pytorch/index.html
                nonlocal curEval

                if torch.is_grad_enabled():
                    optimizer.zero_grad()
                curEval = -evalFunc()
                if curEval.requires_grad:
                    curEval.backward(retain_graph=True)
                return curEval

            prevEval = curEval
            optimizer.step(closure)
            if curEval<prevEval and prevEval-curEval<tol:
                converged = True
            if verbose and iterCount%nIterDisplay==0:
                print(displayFmt%(iterCount, curEval))
            lowerBoundHist.append(-curEval.item())
            iterCount += 1

        return {"lowerBound": -curEval.item(), "lowerBoundHist": lowerBoundHist, "converged": converged}
