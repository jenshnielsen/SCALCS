"""A collection of functions for dwell time ideal, asymptotic and exact
probabulity density function calculations.

Notes
-----
DC_PyPs project are pure Python implementations of Q-Matrix formalisms
for ion channel research. To learn more about kinetic analysis of ion
channels see the references below.

References
----------
CH82: Colquhoun D, Hawkes AG (1982)
On the stochastic properties of bursts of single ion channel openings
and of clusters of bursts. Phil Trans R Soc Lond B 300, 1-59.

HJC92: Hawkes AG, Jalali A, Colquhoun D (1992)
Asymptotic distributions of apparent open times and shut times in a
single channel record allowing for the omission of brief events.
Phil Trans R Soc Lond B 337, 383-404.

CH95a: Colquhoun D, Hawkes AG (1995a)
The principles of the stochastic interpretation of ion channel
mechanisms. In: Single-channel recording. 2nd ed. (Eds: Sakmann B,
Neher E) Plenum Press, New York, pp. 397-482.

CH95b: Colquhoun D, Hawkes AG (1995b)
A Q-Matrix Cookbook. In: Single-channel recording. 2nd ed. (Eds:
Sakmann B, Neher E) Plenum Press, New York, pp. 589-633.
"""

__author__="R.Lape, University College London"
__date__ ="$07-Dec-2010 20:29:14$"

import sys
import math
from decimal import*

import scipy.optimize as so
import numpy as np
from numpy import linalg as nplin

import qmatlib as qml
import bisectHJC
import pdfs
import optimize

def ideal_dwell_time_pdf(t, QAA, phiA):
    """
    Probability density function of the open time.
    f(t) = phiOp * exp(-QAA * t) * (-QAA) * uA
    For shut time pdf A by F in function call.

    Parameters
    ----------
    t : float
        Time (sec).
    QAA : array_like, shape (kA, kA)
        Submatrix of Q.
    phiA : array_like, shape (1, kA)
        Initial vector for openings

    Returns
    -------
    f : float
    """

    kA = QAA.shape[0]
    uA = np.ones((kA, 1))
    expQAA = qml.expQt(QAA, t)
    f = np.dot(np.dot(np.dot(phiA, expQAA), -QAA), uA)
    return f

def ideal_dwell_time_pdf_components(QAA, phiA):
    """
    Calculate time constants and areas for an ideal (no missed events)
    exponential open time probability density function.
    For shut time pdf A by F in function call.

    Parameters
    ----------
    t : float
        Time (sec).
    QAA : array_like, shape (kA, kA)
        Submatrix of Q.
    phiA : array_like, shape (1, kA)
        Initial vector for openings

    Returns
    -------
    taus : ndarray, shape(k, 1)
        Time constants.
    areas : ndarray, shape(k, 1)
        Component relative areas.
    """

    kA = QAA.shape[0]
    w = np.zeros(kA)
    eigs, A = qml.eigs(-QAA)
    uA = np.ones((kA, 1))
    #TODO: remove 'for'
    for i in range(kA):
        w[i] = np.dot(np.dot(np.dot(phiA, A[i]), (-QAA)), uA)

    return eigs, w

def ideal_subset_time_pdf(Q, k1, k2, t):
    """
    
    """
    
    u = np.ones((k2 - k1 + 1, 1))
    phi, QSub = qml.phiSub(Q, k1, k2)
    expQSub = qml.expQt(QSub, t)
    f = np.dot(np.dot(np.dot(phi, expQSub), -QSub), u)
    return f

def ideal_subset_mean_life_time(Q, state1, state2):
    """
    Calculate mean life time in a specified subset. Add all rates out of subset
    to get total rate out. Skip rates within subset.

    Parameters
    ----------
    mec : instance of type Mechanism
    state1,state2 : int
        State numbers (counting origin 1)

    Returns
    -------
    mean : float
        Mean life time.
    """

    k = Q.shape[0]
    p = qml.pinf(Q)
    # Total occupancy for subset.
    pstot = np.sum(p[state1-1 : state2])

    # Total rate out
    s = 0.0
    for i in range(state1-1, state2):
        for j in range(k):
            if (j < state1-1) or (j > state2 - 1):
                s += Q[i, j] * p[i] / pstot

    mean = 1 / s
    return mean

def ideal_mean_latency_given_start_state(mec, state):
    """
    Calculate mean latency to next opening (shutting), given starting in
    specified shut (open) state.

    mean latency given starting state = pF(0) * inv(-QFF) * uF

    F- all shut states (change to A for mean latency to next shutting
    calculation), p(0) = [0 0 0 ..1.. 0] - a row vector with 1 for state in
    question and 0 for all other states.

    Parameters
    ----------
    mec : instance of type Mechanism
    state : int
        State number (counting origin 1)

    Returns
    -------
    mean : float
        Mean latency.
    """

    if state <= mec.kA:
        # for calculating mean latency to next shutting
        p = np.zeros((mec.kA))
        p[state-1] = 1
        uF = np.ones((mec.kA, 1))
        invQFF = nplin.inv(-mec.QAA)
    else:
        # for calculating mean latency to next opening
        p = np.zeros((mec.kF))
        p[state-mec.kA-1] = 1
        uF = np.ones((mec.kF, 1))
        invQFF = nplin.inv(-mec.QFF)

    mean = np.dot(np.dot(p, invQFF), uF)[0]

    return mean

def asymptotic_pdf(t, tres, tau, area):
    """
    Calculate asymptotic probabolity density function.

    Parameters
    ----------
    t : ndarray.
        Time.
    tres : float
        Time resolution.
    tau : ndarray, shape(k, 1)
        Time constants.
    area : ndarray, shape(k, 1)
        Component relative area.

    Returns
    -------
    apdf : ndarray.
    """
    t1 = np.extract(t[:] < tres, t)
    t2 = np.extract(t[:] >= tres, t)
    apdf2 = t2 * pdfs.expPDF(t2 - tres, tau, area)
    apdf = np.append(t1 * 0.0, apdf2)

    return apdf

def asymptotic_roots(tres, QAA, QFF, QAF, QFA, kA, kF):
    """
    Find roots for the asymptotic probability density function (Eqs. 52-58,
    HJC92).

    Parameters
    ----------
    tres : float
        Time resolution (dead time).
    QAA : array_like, shape (kA, kA)
    QFF : array_like, shape (kF, kF)
    QAF : array_like, shape (kA, kF)
    QFA : array_like, shape (kF, kA)
        QAA, QFF, QAF, QFA - submatrices of Q.
    kA : int
        A number of open states in kinetic scheme.
    kF : int
        A number of shut states in kinetic scheme.

    Returns
    -------
    roots : array_like, shape (1, kA)
    """

    sas = -100000
    sbs = -0.0001
    sro = bisectHJC.bisection_intervals(sas, sbs, tres,
        QAA, QFF, QAF, QFA, kA, kF)
    roots = np.zeros(kA)
    for i in range(kA):
        roots[i] = bisectHJC.bisect(sro[i,0], sro[i,1], tres,
            QAA, QFF, QAF, QFA, kA, kF)
    return roots

def asymptotic_areas(tres, roots, QAA, QFF, QAF, QFA, kA, kF, GAF, GFA):
    """
    Find the areas of the asymptotic pdf (Eq. 58, HJC92).

    Parameters
    ----------
    tres : float
        Time resolution (dead time).
    roots : array_like, shape (1,kA)
        Roots of the asymptotic pdf.
    QAA : array_like, shape (kA, kA)
    QFF : array_like, shape (kF, kF)
    QAF : array_like, shape (kA, kF)
    QFA : array_like, shape (kF, kA)
        QAA, QFF, QAF, QFA - submatrices of Q.
    kA : int
        A number of open states in kinetic scheme.
    kF : int
        A number of shut states in kinetic scheme.
    GAF : array_like, shape (kA, kB)
    GFA : array_like, shape (kB, kA)
        GAF, GFA- transition probabilities

    Returns
    -------
    areas : ndarray, shape (1, kA)
    """

    expQFF = qml.expQt(QFF, tres)
    expQAA = qml.expQt(QAA, tres)
    eGAF = qml.eGs(GAF, GFA, kA, kF, expQFF)
    eGFA = qml.eGs(GFA, GAF, kF, kA, expQAA)
    phiA = qml.phiHJC(eGAF, eGFA, kA)

    areas = np.zeros(kA)
    rowA = np.zeros((kA,kA))
    colA = np.zeros((kA,kA))
    for i in range(kA):
        WA = qml.W(roots[i], tres,
            QAA, QFF, QAF, QFA, kA, kF)
        rowA[i] = qml.pinf(WA)
        AW = np.transpose(WA)
        colA[i] = qml.pinf(AW)

    for i in range(kA):
        uF = np.ones((kF,1))
        nom = np.dot(np.dot(np.dot(np.dot(np.dot(phiA, colA[i]), rowA[i]),
            QAF), expQFF), uF)
        W1A = qml.dW(roots[i], tres, QAF, QFF, QFA, kA, kF)
        denom = -roots[i] * np.dot(np.dot(rowA[i], W1A), colA[i])
        areas[i] = nom / denom

    return areas

def exact_pdf(t, tres, roots, areas, eigvals, gamma00, gamma10, gamma11):
    r"""
    Calculate exponential probabolity density function with exact solution for
    missed events correction (Eq. 21, HJC92).

    .. math::
       :nowrap:

       \begin{align*}
       f(t) =
       \begin{cases}
       f_0(t)                          & \text{for}\; 0 \leq t \leq t_\text{res} \\
       f_0(t) - f_1(t - t_\text{res})  & \text{for}\; t_\text{res} \leq t \leq 2 t_\text{res}
       \end{cases}
       \end{align*}

    Parameters
    ----------
    t : float
        Time.
    tres : float
        Time resolution (dead time).
    roots : array_like, shape (k,)
    areas : array_like, shape (k,)
    eigvals : array_like, shape (k,)
        Eigenvalues of -Q matrix.
    gama00, gama10, gama11 : lists of floats
        Coeficients for the exact open/shut time pdf.

    Returns
    -------
    f : float
    """

    if t < tres:
        f = 0
    elif ((tres < t) and (t < (2 * tres))):
        f = qml.f0((t - tres), eigvals, gamma00)
    elif ((tres * 2) < t) and (t < (3 * tres)):
        f = (qml.f0((t - tres), eigvals, gamma00) -
            qml.f1((t - 2 * tres), eigvals, gamma10, gamma11))
    else:
        f = pdfs.expPDF(t - tres, -1 / roots, areas)
    return f

def exact_mean_time(tres, QAA, QFF, QAF, kA, kF, GAF, GFA):
    """
    Calculate exact mean open or shut time from HJC probability density
    function.

    Parameters
    ----------
    tres : float
        Time resolution (dead time).
    QAA : array_like, shape (kA, kA)
    QFF : array_like, shape (kF, kF)
    QAF : array_like, shape (kA, kF)
        QAA, QFF, QAF - submatrices of Q.
    kA : int
        A number of open states in kinetic scheme.
    kF : int
        A number of shut states in kinetic scheme.
    GAF : array_like, shape (kA, kB)
    GFA : array_like, shape (kB, kA)
        GAF, GFA- transition probabilities

    Returns
    -------
    mean : float
        Apparent mean open/shut time.
    """

    expQFF = qml.expQt(QFF, tres)
    expQAA = qml.expQt(QAA, tres)
    eGAF = qml.eGs(GAF, GFA, kA, kF, expQFF)
    eGFA = qml.eGs(GFA, GAF, kF, kA, expQAA)

    phiA = qml.phiHJC(eGAF, eGFA, kA)
    QexpQF = np.dot(QAF, expQFF)
    DARS = qml.dARSdS(tres, QAA, QFF,
        GAF, GFA, expQFF, kA, kF)
    uF = np.ones((kF, 1))
    # meanOpenTime = tres + phiA * DARS * QexpQF * uF
    mean = tres + np.dot(phiA, np.dot(np.dot(DARS, QexpQF), uF))[0]

    return mean

def exact_GAMAxx(mec, tres, open):
    """
    Calculate gama coeficients for the exact open time pdf (Eq. 3.22, HJC90).

    Parameters
    ----------
    tres : float
    mec : dcpyps.Mechanism
        The mechanism to be analysed.
    open : bool
        True for open time pdf and False for shut time pdf.

    Returns
    -------
    eigen : array_like, shape (k,)
        Eigenvalues of -Q matrix.
    gama00, gama10, gama11 : lists of floats
        Constants for the exact open/shut time pdf.
    """

    k = mec.Q.shape[0]
    expQFF = qml.expQt(mec.QFF, tres)
    expQAA = qml.expQt(mec.QAA, tres)
    GAF, GFA = qml.iGs(mec.Q, mec.kA, mec.kF)
    eGAF = qml.eGs(GAF, GFA, mec.kA, mec.kF, expQFF)
    eGFA = qml.eGs(GFA, GAF, mec.kF, mec.kA, expQAA)

    gama00 = []
    gama10 = []
    gama11 = []

    if open:
        phiA = qml.phiHJC(eGAF, eGFA, mec.kA)
        eigen, Z00, Z10, Z11 = qml.Zxx(mec.Q, mec.kA,
            mec.QFF, mec.QAF, mec.QFA, expQFF, open)
        uF = np.ones((mec.kF,1))
        for i in range(k):
            gama00.append(np.dot(np.dot(phiA, Z00[i]), uF)[0])
            gama10.append(np.dot(np.dot(phiA, Z10[i]), uF)[0])
            gama11.append(np.dot(np.dot(phiA, Z11[i]), uF)[0])

    else:
        phiF = qml.phiHJC(eGFA, eGAF, mec.kF)
        eigen, Z00, Z10, Z11 = qml.Zxx(mec.Q, mec.kA,
            mec.QAA, mec.QFA, mec.QAF, expQAA, open)
        uA = np.ones((mec.kA, 1))
        for i in range(k):
            gama00.append(np.dot(np.dot(phiF, Z00[i]), uA)[0])
            gama10.append(np.dot(np.dot(phiF, Z10[i]), uA)[0])
            gama11.append(np.dot(np.dot(phiF, Z11[i]), uA)[0])

    return eigen, np.array(gama00), np.array(gama10), np.array(gama11)

def printout_occupancies(mec, tres, output=sys.stdout):
    """
    """

    output.write('\n\n\n*******************************************\n')
    output.write('\nOpen\tEquilibrium\tMean life\tMean latency (ms)')
    output.write('\nstate\toccupancy\t(ms)\tto next shutting')
    output.write('\n\t\t\tgiven start in this state')

    pinf = qml.pinf(mec.Q)

    for i in range(mec.k):
        if i == 0:
            mean_life_A = ideal_subset_mean_life_time(mec.Q, 1, mec.kA)
            output.write('\nSubset A ' +
                '\t{0:.5g}'.format(np.sum(pinf[:mec.kA])) +
                '\t{0:.5g}'.format(mean_life_A * 1000) +
                '\n')
        if i == mec.kA:
            mean_life_B = ideal_subset_mean_life_time(mec.Q, mec.kA + 1, mec.kA + mec.kB)
            output.write('\n\nShut\tEquilibrium\tMean life\tMean latency (ms)')
            output.write('\nstate\toccupancy\t(ms)\tto next opening')
            output.write('\n\t\t\tgiven start in this state')
            output.write('\nSubset B ' +
                '\t{0:.5g}'.format(np.sum(pinf[mec.kA:mec.kA+mec.kB])) +
                '\t{0:.5g}'.format(mean_life_B * 1000) +
                '\n')
        if i == mec.kE:
            mean_life_C = ideal_subset_mean_life_time(mec.Q, mec.kA + mec.kB + 1, mec.k)
            output.write('\n\nSubset C ' +
                '\t{0:.5g}'.format(np.sum(pinf[mec.kA+mec.kB:mec.k])) +
                '\t{0:.5g}'.format(mean_life_C * 1000) +
                '\n')
        mean = ideal_mean_latency_given_start_state(mec, i+1)
        output.write('\n{0:d}'.format(i+1) +
            '\t{0:.5g}'.format(pinf[i]) +
            '\t{0:.5g}'.format(-1 / mec.Q[i,i] * 1000) +
            '\t{0:.5g}'.format(mean * 1000))

    expQFF = qml.expQt(mec.QFF, tres)
    expQAA = qml.expQt(mec.QAA, tres)
    GAF, GFA = qml.iGs(mec.Q, mec.kA, mec.kF)
    eGAF = qml.eGs(GAF, GFA, mec.kA, mec.kF, expQFF)
    eGFA = qml.eGs(GFA, GAF, mec.kF, mec.kA, expQAA)
    phiA = qml.phiHJC(eGAF, eGFA, mec.kA)
    phiF = qml.phiHJC(eGFA, eGAF, mec.kF)

    output.write('\n\n\nInitial HJC vector for openings phiOp =\n')
    for i in range(phiA.shape[0]):
        output.write('\t{0:.5g}'.format(phiA[i]))
    output.write('\n\nInitial HJC vector for shuttings phiSh =\n')
    for i in range(phiF.shape[0]):
        output.write('\t{0:.5g}'.format(phiF[i]))


def printout_distributions(mec, tres, output=sys.stdout, eff='c'):
    """

    """

    output.write('\n\n\n*******************************************\n')
    GAF, GFA = qml.iGs(mec.Q, mec.kA, mec.kF)
    # OPEN TIME DISTRIBUTIONS
    open = True
    # Ideal pdf
    eigs, w = ideal_dwell_time_pdf_components(mec.QAA,
        qml.phiA(mec))
    output.write('\nIDEAL OPEN TIME DISTRIBUTION')
    pdfs.expPDF_printout(eigs, w, output)

    # Asymptotic pdf
    #roots = asymptotic_roots(mec, tres, open)
    roots = asymptotic_roots(tres,
        mec.QAA, mec.QFF, mec.QAF, mec.QFA, mec.kA, mec.kF)
    #areas = asymptotic_areas(mec, tres, roots, open)
    areas = asymptotic_areas(tres, roots,
        mec.QAA, mec.QFF, mec.QAF, mec.QFA, mec.kA, mec.kF, GAF, GFA)
    output.write('\n\nASYMPTOTIC OPEN TIME DISTRIBUTION')
    output.write('\nterm\ttau (ms)\tarea (%)\trate const (1/sec)')
    for i in range(mec.kA):
        output.write('\n{0:d}'.format(i+1) +
        '\t{0:.5g}'.format(-1.0 / roots[i] * 1000) +
        '\t{0:.5g}'.format(areas[i] * 100) +
        '\t{0:.5g}'.format(- roots[i]))
    areast0 = np.zeros(mec.kA)
    for i in range(mec.kA):
        areast0[i] = areas[i] * np.exp(- tres * roots[i])
    areast0 = areast0 / np.sum(areast0)
    output.write('\nAreas for asymptotic pdf renormalised for t=0 to\
    infinity (and sum=1), so areas can be compared with ideal pdf.')
    for i in range(mec.kA):
        output.write('\n{0:d}'.format(i+1) +
        '\t{0:.5g}'.format(areast0[i] * 100))
    mean = exact_mean_time(tres,
            mec.QAA, mec.QFF, mec.QAF, mec.kA, mec.kF, GAF, GFA)
    output.write('\nMean open time (ms) = {0:.5g}'.format(mean * 1000))

    # Exact pdf
    eigvals, gamma00, gamma10, gamma11 = exact_GAMAxx(mec, tres, open)
    output.write('\n\nEXACT OPEN TIME DISTRIBUTION')
    output.write('\neigen\tg00(m)\tg10(m)\tg11(m)')
    for i in range(mec.k):
        output.write('\n{0:.5g}'.format(eigvals[i]) +
        '\t{0:.5g}'.format(gamma00[i]) +
        '\t{0:.5g}'.format(gamma10[i]) +
        '\t{0:.5g}'.format(gamma11[i]))

    output.write('\n\n\n*******************************************\n')
    # SHUT TIME DISTRIBUTIONS
    open = False
    # Ideal pdf
    eigs, w = ideal_dwell_time_pdf_components(mec.QFF, qml.phiF(mec))
    output.write('\nIDEAL SHUT TIME DISTRIBUTION')
    pdfs.expPDF_printout(eigs, w, output)

    # Asymptotic pdf
    #roots = asymptotic_roots(mec, tres, open)
    roots = asymptotic_roots(tres,
        mec.QFF, mec.QAA, mec.QFA, mec.QAF, mec.kF, mec.kA)
    #areas = asymptotic_areas(mec, tres, roots, open)
    areas = asymptotic_areas(tres, roots,
        mec.QFF, mec.QAA, mec.QFA, mec.QAF, mec.kF, mec.kA, GFA, GAF)
    output.write('\n\nASYMPTOTIC SHUT TIME DISTRIBUTION')
    output.write('\nterm\ttau (ms)\tarea (%)\trate const (1/sec)')
    for i in range(mec.kF):
        output.write('\n{0:d}'.format(i+1) +
        '\t{0:.5g}'.format(-1.0 / roots[i] * 1000) +
        '\t{0:.5g}'.format(areas[i] * 100) +
        '\t{0:.5g}'.format(- roots[i]))
    areast0 = np.zeros(mec.kF)
    for i in range(mec.kF):
        areast0[i] = areas[i] * np.exp(- tres * roots[i])
    areast0 = areast0 / np.sum(areast0)
    output.write('\nAreas for asymptotic pdf renormalised for t=0 to\
    infinity (and sum=1), so areas can be compared with ideal pdf.')
    for i in range(mec.kF):
        output.write('\n{0:d}'.format(i+1) +
        '\t{0:.5g}'.format(areast0[i] * 100))
    mean = exact_mean_time(tres,
            mec.QFF, mec.QAA, mec.QFA, mec.kF, mec.kA, GFA, GAF)
    output.write('\nMean shut time (ms) = {0:.6f}'.format(mean * 1000))

    # Exact pdf
    eigvals, gamma00, gamma10, gamma11 = exact_GAMAxx(mec, tres, open)
    output.write('\n\nEXACT SHUT TIME DISTRIBUTION')
    output.write('\neigen\tg00(m)\tg10(m)\tg11(m)')
    for i in range(mec.k):
        output.write('\n{0:.5g}'.format(eigvals[i]) +
        '\t{0:.5g}'.format(gamma00[i]) +
        '\t{0:.5g}'.format(gamma10[i]) +
        '\t{0:.5g}'.format(gamma11[i]))

def printout_tcrit(mec, output=sys.stdout):
    """
    Output calculations based on division into bursts by critical time (tcrit).

    Parameters
    ----------
    mec : dcpyps.Mechanism
        The mechanism to be analysed.
    output : output device
        Default device: sys.stdout
    """

    output.write('\n\n\n*******************************************\n')
    output.write('CALCULATIONS BASED ON DIVISION INTO BURSTS BY' +
    ' tcrit- CRITICAL TIME.\n')
    # Ideal shut time pdf
    eigs, w = ideal_dwell_time_pdf_components(mec.QFF, qml.phiF(mec))
    output.write('\nIDEAL SHUT TIME DISTRIBUTION')
    pdfs.expPDF_printout(eigs, w, output)
    taus = 1 / eigs
    areas = w /eigs
    taus, areas = optimize.sortShell2(taus, areas)

    comps = taus.shape[0]-1
    tcrits = np.empty((3, comps))
    for i in range(comps):
        output.write('\n\nCritical time between components {0:d} and {1:d}'.
            format(i+1, i+2))
        output.write('\n\nEqual % misclassified (DC criterion)')
        tcrit = so.bisect(pdfs.expPDF_tcrit_DC,
            taus[i], taus[i+1], args=(taus, areas, i+1))
        tcrits[0, i] = tcrit
        enf, ens, pf, ps = pdfs.expPDF_misclassified(tcrit, taus, areas, i+1)
        pdfs.expPDF_misclassified_printout(tcrit, enf, ens, pf, ps, output)
        output.write('\nEqual # misclassified (Clapham & Neher criterion)')
        tcrit = so.bisect(pdfs.expPDF_tcrit_CN,
            taus[i], taus[i+1], args=(taus, areas, i+1))
        tcrits[1, i] = tcrit
        enf, ens, pf, ps = pdfs.expPDF_misclassified(tcrit, taus, areas, i+1)
        pdfs.expPDF_misclassified_printout(tcrit, enf, ens, pf, ps, output)
        output.write('\nMinimum total # misclassified (Jackson et al criterion)')
        tcrit = so.bisect(pdfs.expPDF_tcrit_Jackson,
            taus[i], taus[i+1], args=(taus, areas, i+1))
        tcrits[2, i] = tcrit
        enf, ens, pf, ps = pdfs.expPDF_misclassified(tcrit, taus, areas, i+1)
        pdfs.expPDF_misclassified_printout(tcrit, enf, ens, pf, ps, output)

    output.write('\n\nSUMMARY of tcrit values:')
    output.write('\nComponents  DC\tC&N\tJackson\n')
    for i in range(comps):
        output.write('{0:d} to {1:d} '.format(i+1, i+2) +
            '\t{0:.5g}'.format(tcrits[0, i] * 1000) +
            '\t{0:.5g}'.format(tcrits[1, i] * 1000) +
            '\t{0:.5g}\n'.format(tcrits[2, i] * 1000))

