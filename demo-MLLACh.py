#! /usr/bin/python
"""
Maximum likelihood fit demo.
"""

import sys
import time
import numpy as np
import cProfile

from dcpyps import optimize
from dcpyps import dcio
from dcpyps import dataset
from dcpyps import scalcslib as scl
from dcpyps import mechanism

def main():

    # LOAD MECHANISM USED IN COLQUHOUN et al 2003.
    mecfn = "./dcpyps/samples/demomec.mec"
    version, meclist, max_mecnum = dcio.mec_get_list(mecfn)
    mec = dcio.mec_load(mecfn, meclist[1][0])

    mec.printout(sys.stdout)
    tres = 0.000025
    tcrit = 0.0035
    conc = 50e-9

    # LOAD DATA.
    filename = "./dcpyps/samples/AChsim.scn"
    ioffset, nint, calfac, header = dcio.scn_read_header(filename)
    tint, iampl, iprops = dcio.scn_read_data(filename, ioffset, nint, calfac)
    rec1 = dataset.SCRecord(filename, header, tint, iampl, iprops)
    # Impose resolution, get open/shut times and bursts.
    rec1.impose_resolution(tres)
    rec1.get_open_shut_periods()
    rec1.get_bursts(tcrit)
    print('\nNumber of resolved intervals = {0:d}'.format(len(rec1.rtint)))
    print('\nNumber of bursts = {0:d}'.format(len(rec1.bursts)))
    blength = rec1.get_burst_length_list()
    print('Average length = {0:.9f} ms'.format(np.average(blength)*1000))
#    print('Range: {0:.3f}'.format(min(blength)) +
#            ' to {0:.3f} millisec'.format(max(blength)))
    openings = rec1.get_openings_burst_list()
    print('Average number of openings= {0:.9f}'.format(np.average(openings)))

    # PREPARE RATE CONSTANTS.
    # Fixed rates.
    fixed = np.array([False, False, False, False, False, False, False, True,
        False, False, False, False, False, False])
    if fixed.size == len(mec.Rates):
        for i in range(len(mec.Rates)):
            mec.Rates[i].fixed = fixed[i]

    # Constrained rates.
    mec.Rates[6].is_constrained = True
    mec.Rates[6].constrain_func = mechanism.constrain_rate_multiple
    mec.Rates[6].constrain_args = [10, 1]
    mec.Rates[8].is_constrained = True
    mec.Rates[8].constrain_func = mechanism.constrain_rate_multiple
    mec.Rates[8].constrain_args = [12, 1]
    mec.Rates[9].is_constrained = True
    mec.Rates[9].constrain_func = mechanism.constrain_rate_multiple
    mec.Rates[9].constrain_args = [13, 1]

    mec.Rates[11].mr=True

    mec.update_constrains()
    mec.update_mr()

    # Initial guesses. Now using rate constants from numerical example.
    rates = np.log(mec.unit_rates())
    mec.set_rateconstants(np.exp(rates))
    mec.printout(sys.stdout)
    theta = mec.theta()
    print '\n\ntheta=', theta

    # Prepare parameter dict for simplex
    opts = {}
    opts['mec'] = mec
    opts['conc'] = conc
    opts['tres'] = tres
    opts['tcrit'] = tcrit
    opts['isCHS'] = True
    opts['data'] = rec1.bursts

    # MAXIMUM LIKELIHOOD FIT.
    start_lik, th = scl.HJClik(np.log(theta), opts)
    print ("Starting likelihood = {0:.6f}".format(-start_lik))
    print ("\nFitting started: %4d/%02d/%02d %02d:%02d:%02d\n"
            %time.localtime()[0:6])
    xout, fout, niter, neval = optimize.simplex(scl.HJClik,
        np.log(theta), args=opts, display=True)
    print ("\nFitting finished: %4d/%02d/%02d %02d:%02d:%02d\n"
            %time.localtime()[0:6])
    # Display results.
    mec.theta_unsqueeze(np.exp(xout))
    print "\n Final rate constants:"
    mec.printout(sys.stdout)
    print ('\n Final log-likelihood = {0:.6f}'.format(-fout))
    print ('\n Number of evaluations = {0:d}'.format(neval))
    print ('\n Number of iterations = {0:d}'.format(niter))
    print '\n\n'

try:
    cProfile.run('main()')
except KeyboardInterrupt:
    pass
