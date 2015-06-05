#!/usr/bin/env python
#
# Last modified: Time-stamp: <2015-06-05 17:36:23 Sara>

"""Quality control (QC) functions for CODAR SeaSonde Radialmetric data

QC categories:
A. Threshold Tests -- badflag any values that fall below or above a single threshold
B. Range Tests -- badflag values that fall outside of a range
C. Weighted Averaging -- average several values with weights based on signal quality parameters 

QC Range Tests:
NONE TO DO YET

QC Threshold Tests:
1. DOA peak power (MSR1, MDR1, MDR2) < 5 dB default 
2. DOA 1/2 power width (3dB down) (MSW1, MDW1, MDW2) > 50 deg default
3. SNR on monopole (MA3S) < 5 dB default

Weighted Averaging:
1. Weighting based on Music Power (MSP1, MDP1, MDP2)
2. Weighting based on SNR on monopole (MA3S)
3. No weight function (None) 

"""
import sys
import os
import re
import fnmatch
import datetime

import numpy
numpy.set_printoptions(suppress=True)

# 
from codarutils import *

def _commonly_assigned_columns():
    """
    Commonly assigned CODAR RadialMetric columns
    """
    # for cut and pasting to other functions
    # help make some code more readable
    VFLG = c['VFLG']
    MSEL = c['MSEL']
    MSR1 = c['MSR1']
    MDR1 = c['MDR1']
    MDR2 = c['MDR2']
    MSW1 = c['MSW1'] 
    MDW1 = c['MDW1']
    MDW2 = c['MDW2']
    MA3S = c['MA3S']

def threshold_qc_doa_peak_power(d, types_str, threshold=5.0):
    """Bad Flag any DOA peak power (dB) less than threshold value (default 5.0 dB).

    Flags any direction of arrival (DOA) peak power (dB) that falls
    below the input threshold value (default 5.0 dB).  Depending on
    the value of MSEL (1, 2, or 3), MSR1, MDR1, or MDR2 columns are
    evaluated.  Returns modified matrix with VFLG column the only
    changed values.

    """
    c = get_columns(types_str)
    VFLG = c['VFLG'] # help make the test more readable
    MSEL = c['MSEL']
    MSR1 = c['MSR1']
    MDR1 = c['MDR1']
    MDR2 = c['MDR2']
    d1=numpy.copy(d)
    # 
    havenan = numpy.isnan(d[:,MSR1]) | numpy.isnan(d[:,MDR1]) | numpy.isnan(d[:,MDR2])
    bad = ((d[:,MSEL]==1) & (d[:,MSR1]<float(threshold))) | \
          ((d[:,MSEL]==2) & (d[:,MDR1]<float(threshold))) | \
          ((d[:,MSEL]==3) & (d[:,MDR2]<float(threshold))) | havenan
    d1[bad, VFLG] = d[bad,VFLG]+(1<<1)
    return d1

def threshold_qc_doa_half_power_width(d, types_str, threshold=50.0):
    """Bad Flag DOA 1/2 Power Width (degress) greater than threshold value (default 50.0 degrees).

    Flags any direction of arrival (DOA) 1/2 Power width (degress)
    that is wider than the input threshold value (default 50.0
    degrees).  Depending on the value of MSEL (1, 2, or 3), MSW1,
    MDW1, or MDW2 columns are evaluated.  Returns modified matrix with
    VFLG column the only changed values.

    """
    c = get_columns(types_str)
    VFLG = c['VFLG'] # help make the test more readable
    MSEL = c['MSEL']
    MSW1 = c['MSW1'] 
    MDW1 = c['MDW1']
    MDW2 = c['MDW2']
    d2=numpy.copy(d)
    # 
    havenan = numpy.isnan(d[:,MSW1]) | numpy.isnan(d[:,MDW1]) | numpy.isnan(d[:,MDW2])
    bad = ((d[:,MSEL]==1) & (d[:,MSW1]>float(threshold))) | \
          ((d[:,MSEL]==2) & (d[:,MDW1]>float(threshold))) | \
          ((d[:,MSEL]==3) & (d[:,MDW2]>float(threshold))) | havenan
    d2[bad, VFLG] = d[bad,VFLG]+(1<<2)
    return d2

def threshold_qc_monopole_snr(d, types_str, threshold=5.0):
    """Bad flag any SNR on monopole (dB)  less than threshold value (default 5.0 dB).

    Flags any signal-to-noise ratio (SNR) on monopole (dB) that falls
    below the input threshold value (default 5.0 dB) for all MSEL selections.

    """
    # Test 3 SNR on monopole (dB) for all selections
    # 
    c = get_columns(types_str)
    VFLG = c['VFLG'] # help make the test more readable
    MA3S = c['MA3S']
    d3=numpy.copy(d)
    # 
    bad = d[:,MA3S]<float(threshold)
    d3[bad, VFLG] = d[bad,VFLG]+(1<<3)
    return d3

def threshold_qc_all(d, types_str, thresholds=[5.0, 50.0, 5.0]):
    """Combine all three threshold tests

    Returns modified matrix with VFLG column only changed values.

    """
    # TO DO: Use a dict or list to pass thresholds for all tests ??
    # if dict what key to use
    # if list how know the correct order for tests
    # 
    dall = threshold_qc_doa_peak_power(d, types_str, thresholds[0])
    dall = threshold_qc_doa_half_power_width(dall, types_str, thresholds[1])
    dall = threshold_qc_monopole_snr(dall, types_str, thresholds[2])
    return dall


def weighted_velocities(d, types_str, bearing_spread=1.0, weight_parameter='MP'):
    """Calculates weighted average of radial velocities (VELO) at bearing and range.

    The weighted average of velocities found at given range and
    bearing based on weight_parameter.

    Paramters
    ---------
    d : ndarray
        The data from LLUV file(s). 
    types_str : string 
        The 'TalbleColumnTypes' string header of LLUV file(s) provide keys for each column.
    weight_parameter : string ('MP', 'SNR3', 'NONE'), optional 
        If 'MP' (default), uses MUSIC antenna peak power values for weighting function
           using MSEL to select one of (MSP1, MDP1, or MDP2).
        If 'SNR3', uses signal-to-noise ratio on monopole (MA3S).
        If 'NONE', just average with no weighting performed.
    bearing_spread: float, optional (default 1.0 degree)
       The number of degrees to look adjacent to either side of
       current bearing for increase spatial coverage (and potentially
       the sample size) for the average.
       For example, 
          If 0.0, velocities from window of 1 deg will be averaged.
          If 1.0, velocities from a window of 3 degrees will be avearged. This is the default.
          If 2.0, velocities from a window of 5 degrees

    Returns
    -------
    xd : ndarray
       The averaged values with range and bearing.
       An array with averaged values, range, bearing, 
    xtypes_str : string 
        The order and key-labels for each column of xd array

    """
    c = get_columns(types_str)
    offset = bearing_spread # 0 is default but can use 1 or 2 to get 3 or 5 deg spread
    # 
    ud = unique_rows(d[:,[c['SPRC'],c['BEAR'],c['VFLG']]].copy())
    # return only rows that have VFLG==0 (0 == good, >0 bad) so only get good data
    ud = ud[ud[:,2]==0]
    # sort this array based on rangecell (SPRC) and bearing (BEAR), remember last (col=0) is first to sort 
    idx = numpy.lexsort((ud[:,1], ud[:,0]))
    ud = ud[idx,:]
    # 
    # order of columns and labels for output data
    xtypes_str = 'SPRC BEAR VELO ESPC MAXV MINV EDVC ERSC'
    xc = get_columns(xtypes_str)
    #
    nrows, _ = ud.shape
    ncols = len(xc)
    xd = numpy.ones(shape=(nrows,ncols))*numpy.nan
    #
    for irow, cell in enumerate(ud):
        rngcell, bearing = cell[0:2]
        # numpy.where() returns a tuple for condition so use numpy.where()[0]
        # also VFLG must equal 0 (0 == good, >0 bad) so only get good data
        xrow = numpy.where((d[:,c['SPRC']]==rngcell) & \
                           (d[:,c['BEAR']]>=bearing-offset) & \
                           (d[:,c['BEAR']]<=bearing+offset) & \
                           (d[:,c['VFLG']]==0))[0]
        # If no row matches rngcell AND bearing, then no VELO data, skip to next bearing
        if xrow.size == 0: 
            continue
        
        xcol = numpy.array([c['VELO'], c['MSEL'], c['MSP1'], c['MDP1'], c['MDP2'], c['MA3S']])
        a = d[numpy.ix_(xrow, xcol)].copy()
        # if xrow.size == edvc:
        VELO = a[:,0] # all radial velocities found in cell
        SNR3 = a[:,5] # SNR on monopole for each velocity
        if weight_parameter.upper() == 'MP':
            # Create array to hold each Music Power (based on MSEL)
            MP = numpy.array(numpy.ones(VELO.shape)*numpy.nan) 
            # pluck the msel-based Music Power from MSP1, MDP1 or MPD2 column
            for msel in [1, 2, 3]:
                which = a[:,1]==msel
                MP[which,] = a[which, msel+1]
            # convert MP from db to voltage for weighting
            MP = numpy.power(10, MP/10.)
            wts = MP/MP.sum()
            velo = numpy.dot(VELO,wts)
        elif weight_parameter.upper() == 'SNR3' or weight_parameter.upper() == 'SNR':
            wts = SNR3/SNR3.sum()
            velo = numpy.dot(VELO,wts)
        elif weight_parameter.upper() == 'NONE':
            # do no weighting and just compute the mean of all velo's
            velo = VELO.mean()
        # data
        xd[irow,xc['SPRC']] = rngcell
        xd[irow,xc['BEAR']] = bearing
        xd[irow,xc['VELO']] = velo
        # other stat output
        xd[irow,xc['ESPC']] = VELO.std() # ESPC
        xd[irow,xc['MAXV']] = VELO.max() # MAXV
        xd[irow,xc['MINV']] = VELO.min() # MINV
        # (EDVC and ERSC are the same in this subroutine's context)
        xd[irow,xc['EDVC']] = VELO.size # EDVC Velocity Count 
        xd[irow,xc['ERSC']] = VELO.size # ERSC Spatial Count
                
    return xd, xtypes_str

def generate_radialshort_array(d, types_str, table_type='LLUV RDL7'):
    """Generates radialshort (rsd) data array.

    This function generates radialshort data (rsd) array by merging
    unique rows of original radialmetric data (d).  It is intended to be
    the output CSV data table (middle) of CODAR LLUV format with header,
    middle, and footer.
    
    Parameters
    ----------
    d : ndarray
       The original radialmetric data for extracting lat, lon, etc.
    types_str : string 
        The order and key-labels for each column of xd array.
    table_type : string

    Returns
    -------
    rsd : ndarray
       The generated radialshort (rsd) data from merging unique rows
       of rangecell and bearing.
    rsdtypes_str : string 
        The order and key-labels for each column of rsd array.

    """
    if table_type == 'LLUV RDL7':
        rsdtypes_str = 'LOND LATD VELU VELV VFLG ESPC MAXV MINV EDVC ERSC XDST YDST RNGE BEAR VELO HEAD SPRC'
    else:
        print 'generate_radial_array() : Unrecognized table_type "%s"' % (table_type,)
        return numpy.array([]), ''

    # 
    # get unique rows of rangecells and bearings based on input radialmetric data
    # but also collect columns of info so we don't have to reproduce in next steps
    c = get_columns(types_str)
    dcol = numpy.array([c['LOND'], c['LATD'], c['VFLG'], c['RNGE'], c['BEAR'], c['SPRC']])
    ud = unique_rows(d[:,dcol].copy())
    # return only rows that have VFLG==0 (0 == good, >0 bad) so only get good data
    ud = ud[ud[:,2]==0]
    # sort this array based on rangecell (SPRC) and bearing (BEAR)
    idx = numpy.lexsort((ud[:,4], ud[:,5]))
    ud = ud[idx,:]
    # 
    # order of columns and labels for output data
    rsc = get_columns(rsdtypes_str)
    nrows,_ = ud.shape
    ncols = len(rsc)
    # Initialize new array for radial shorts
    rsd = numpy.ones(shape=(nrows,ncols))*numpy.nan
    # Distribute data in to new array 
    rscol = numpy.array([rsc['LOND'], rsc['LATD'], rsc['VFLG'], rsc['RNGE'], rsc['BEAR'], rsc['SPRC']])
    rsd[:,rscol] = ud
    return rsd, rsdtypes_str
    

def fill_radialshort_array(rsd, rsdtypes_str, xd, xtypes_str):
    """Fill in radialshort (rsd) data. 

    This function fills radialshort data (rsd) by merging rows of
    averaged velocity data (xd) where rangecell and bearing match.

    Parameters
    ----------
    rsd : ndarray
       The generated radialshort (rsd) data from generate_radialshort_array().
    rsdtypes_str : string 
        The order and key-labels for each column of rsd array.
    xd : ndarray
       The array with averaged values, range, bearing, and other stats used to fill in rsd array.
    xtypes_str : string 
        The order and key-labels for each column of xd array.

    Returns
    -------
    rsd : ndarray
       The modified radialshort (rsd) data.
    rsdtypes_str : string 
        The order and key-labels for each column of rsd array.

    """

    rsc = get_columns(rsdtypes_str)
    rscells = rsd[:,[rsc['SPRC'], rsc['BEAR']]]
    rscol = numpy.array([rsc['VELO'], rsc['ESPC'], rsc['MAXV'], rsc['MINV'], rsc['EDVC'], rsc['ERSC']])

    xc = get_columns(xtypes_str)
    xcells = xd[:,[xc['SPRC'],xc['BEAR']]]
    xcol = numpy.array([xc['VELO'], xc['ESPC'], xc['MAXV'], xc['MINV'], xc['EDVC'], xc['ERSC']])

    # check range and bearing columns are the same between rsd and xd
    assert rscells.shape == xcells.shape, "rscells.shape(%d,%d)" % rscells.shape 
    assert (rscells == xcells).all()
    # deal xd data into rsd by columns
    rsd[:,rscol] = xd[:,xcol]

    # if not, then match row-by-row, and deal each row as matches are made
    # for rngcell, bearing in rsd[:10, [rsc['SPRC'],rsc['BEAR']]]:
    #     print "rangecell: %d, bearing: %d" % (rngcell, bearing)

    # create HEAD column based on BEAR+180
    bear = rsd[:,rsc['BEAR']]
    head = numpy.mod(bear+180., 360.)
    velo = rsd[:,rsc['VELO']]
    # compute velocity components
    (velu, velv) = compass2uv(velo, head)
    # replace VELU, VELV, HEAD in radial short data
    rsd[:,rsc['VELU']]=velu
    rsd[:,rsc['VELV']]=velv
    rsd[:,rsc['HEAD']]=head
    #
    rnge = rsd[:,rsc['RNGE']]
    (xdist, ydist) = compass2uv(rnge,bear)
    # relace XDIST, YDIST in radial short data
    rsd[:,rsc['XDST']]=xdist
    rsd[:,rsc['YDST']]=ydist
    
    return rsd, rsdtypes_str

def generate_radialshort_header(rsd, rsdtypes_str, header):
    """ Fill radialshort header details from radialmetric header

    Replaces lines from input radialmetric header that start with '%
    Table*' and '%% ' to match radialshort format.  Information gleaned
    from rsd and rdstypes_str are used in header metadata.

    Note: this could be generalized for any LLUV file since passing in info
    create lines that describe the main data. LLUV RDL7 is specified in
    generate_radialshort_array() as is the rsdtypes_str defining columns.

    Parameter:
    ----------
    rsd : ndarray
       The radialshort (rsd) data.
    rsdtypes_str : string 
        The order and key-labels for each column of rsd array.
    header : string
       The radialmetric header

    Returns:
    --------
    rsdheader : string
       The radialshort header
    """

    # keep everything up until TableType
    rsdheader = re.split(r'(\n%TableType)', header)[0]

    ncols_from_string = len(rsdtypes_str.split(' '))
    nrows, ncols = rsd.shape
    assert ncols == ncols_from_string, 'ncols from rsdtypes_str and rsd ncols do not match'

    lines = rsdheader.split('\n')
    # add following lines to header string to conform to radialshort data type
    lines.append('%' + 'TableType: LLUV RDL7')
    lines.append('%' + 'TableColumns: %d' % ncols)
    lines.append('%' + 'TableColumnTypes: %s' % rsdtypes_str)
    lines.append('%' + 'TableRows: %d' % nrows)
    lines.append('%TableStart:')
    lines.append('%%   Longitude   Latitude    U comp   V comp  VectorFlag    Spatial     Velocity    '+\
                 'Velocity  Velocity Spatial  X Distance  Y Distance   Range   Bearing   Velocity  '+\
                 'Direction   Spectra')
    lines.append('%%     (deg)       (deg)     (cm/s)   (cm/s)  (GridCode)    Quality     Maximum     '+\
                 'Minimum    Count    Count      (km)        (km)       (km)    (True)    (cm/s)     '+\
                 '(True)    RngCell')
    return '\n'.join(lines)

def unique_rows(a):
    # http://stackoverflow.com/questions/8560440/removing-duplicate-columns-and-rows-from-a-numpy-2d-array?lq=1
    a = numpy.ascontiguousarray(a)
    unique_a = numpy.unique(a.view([('', a.dtype)]*a.shape[1]))
    return unique_a.view(a.dtype).reshape((unique_a.shape[0], a.shape[1]))

def cell_intersect(rngbear1, rngbear2):
    """ Return rows that match range and bearing data between the two nx2 matrices.

    Parameters
    ----------
    rngbear1 : nx2 array
       The first array of range and bearings that define each cell. 
       The first column is range cells.  The second column are the bearings.
    rngbear2 : nx2 array
       The second array of range and bearings that define each cell. 
       The first column is range cells.  The second column are the bearings.
    
    Return
    ------
    (rows1, rows2) : tuple of nx1 arrays 
       The rows where range and bearing cell are the same between two input matrices.
    """
    rows1 = []; rows2=[]
    for irow, cell in enumerate(rngbear1):
        rngcell, bearing = cell
        xrow = numpy.where( (rngbear2[:, 0] == rngcell) & \
                            (rngbear2[:, 1] == bearing) )[0]
        if xrow.size == 0:
            continue
        rows1.append(irow); rows2.append(xrow)
    rows1 = numpy.squeeze(rows1)
    rows2 = numpy.squeeze(rows2)
    return (rows1, rows2)


def compass2uv(wmag, wdir):
    """ Vector conversion from mag and direction (wmag,wdir) to x,y
    vector components (u,v)

    If inputs are lists, it is cast into an arrays.

    Parameters
    ----------
    wmag : array-like, same size as wdir
       The magnitude of the vector. 
    wdir : array-like, same size as wmag
       The compass direction, Clockwise from y-axis or North equals 0/360 deg

    Returns
    -------
    (u,v) : tuple of array-like u and v vectors the same size and shape as inputs.
       The x,y vector components. 

    >>> compass2uv(1.0, 0.0)
    (0.0, 1.0)
    >>> compass2uv([1., 1., 1., 1.], [0., 90., 180., 270.])
    (array([ 0.,  1.,  0., -1.]), array([ 1.,  0., -1., -0.]))
    
    """
    # calculate horizontal vector components (u,v) from magnitude and compass direction
    # cast the inputs into numpy.array
    wmag = numpy.array(wmag)
    wdir = numpy.array(wdir)
    assert wmag.shape == wdir.shape, 'wmag and wdir must be same size and shape'
    
    r = numpy.pi/180.
    u = wmag*numpy.sin(wdir*r)
    v = wmag*numpy.cos(wdir*r)
    return (u,v)

def recursive_glob(treeroot, pattern):
    """ Glob-like search for filenames based on pattern but in all
    subdirectories to treeroot.

    Parameters
    ----------
    treeroot : string
       The top most directory path to begin search.
    pattern : string
       The pattern to match file in search.

    Return
    ------
    results : list of paths
       The results of search.

    >>> files = os.path.join(os.path.curdir, 'test', 'files')
    >>> recursive_glob(files, 'RDLx*.*')
    ['.\\test\\files\\codar_raw\\Radialshorts_HATY_2013_11_05\\RDLx_HATY_2013_11_05_0000.ruv',
    '.\\test\\files\\RadialShorts_mp_weight_angres1\\RDLx_HATY_2013_11_05_0000.ruv',
    '.\\test\\files\\RadialShorts_mp_weight_angres3\\RDLx_HATY_2013_11_05_0000.ruv',
    '.\\test\\files\\RadialShorts_no_weight_angres1\\RDLx_HATY_2013_11_05_0000.ruv',
    '.\\test\\files\\RadialShorts_snr_weight_angres1\\RDLx_HATY_2013_11_05_0000.ruv',
    '.\\test\\files\\RadialShorts_snr_weight_angres3\\RDLx_HATY_2013_11_05_0000.ruv']
    
    """
    # fnmatch gives you exactly the same patterns as glob, so this is
    # really an excellent replacement for glob.glob with very close
    # semantics.  Pasted from
    # <http://stackoverflow.com/questions/2186525/use-a-glob-to-find-files-recursively-in-python>
    results = [] 
    for base, dirs, files in os.walk(treeroot): 
        goodfiles = fnmatch.filter(files, pattern) 
        results.extend(os.path.join(base, f) for f in goodfiles) 
    return results 

def _find_files():
    # one of the utilities for qc codar is to aggregate several sample times of data before qc'ing and doing
    # weighted average
    #
    # if interested in loading a targe site, date and time e.g. RDLv_HATY_2013_11_05_0000.ruv,
    # then we nned to first find it and the other
    # files (one before and one after) if they exist.
    # Need to know OutputTimeInterval (30 min in this case) to know what was previous file(s) and
    # next file(s) look like
    #
    # Most likely they will be in same directory but they might not
    # 
    # test/files/codar_raw/Radialmetric_HATY_2013_11_04/RDLv_HATY_2013_11_04_2330.ruv 
    # test/files/codar_raw/Radialmetric_HATY_2013_11_05/RDLv_HATY_2013_11_05_0000.ruv 
    # test/files/codar_raw/Radialmetric_HATY_2013_11_05/RDLv_HATY_2013_11_05_0030.ruv
    files = recursive_glob(os.path.join(files, 'codar_raw'), 'RDLv*.ruv')
    for f in files:
        fn = os.path.split(f)[-1]
        fndt = filt_datetime(fn)

    target
    dt_start = dts[0]-datetime.timedelta(minutes=30)
    dt_end = dts[0]+datetime.timedelta(minutes=30)

def filt_datetime(input_string):
    """ Attempts to filter date and time from input string.
    
    Following the template, YYYY(-)MM(-)DD(-)(hh(:)(mm(:)(ss)))
    find the most precise, reasonable string match and
    return its datetime object.

    Typical matches include, YYYYMMDD-hhmmss, YYYY-MM-DD-hh:mm:ss

    Requires date with all three (year, month, day) in decreasing
    order as integers. Time is optional.
    
    """
    # typical codar time stamp format
    pattern = r"""
    # YYYY(-)MM(-)DD(-)(hh(:)(mm(:)(ss)))
    (\d{4})           # 4-digit YEAR 
    \D?               # optional 1 character non-digit separator (e.g. ' ' or '-')
    (\d{2})           # 2-digit MONTH 
    \D?               # optional 1 character non-digit separator
    (\d{2})           # 2-digit DAY 
    \D?               # optional 1 character non-digit separator (e.g. ' ' or 'T')
    (\d{2})?          # optional 2-digit HOUR 
    \D?               # optional 1 character non-digit separator (e.g. ' ' or ':')
    (\d{2})?          # optional 2-digit MINUTE 
    \D?               # optional 1 character non-digit separator (e.g. ' ' or ':')
    (\d{2})?          # optional 2-digit SECOND
    """
    p = re.compile(pattern, re.VERBOSE)
    # input_string = 'RDLv_HATY_2013_11_05_000000.ruv'
    # input_string = 'RDLv_HATY_2013_11_05_0000.ruv'
    # input_string = 'RDLv_HATY_2013_11_05_00.ruv'
    # input_string = 'RDLv_HATY_2013_11_05.ruv'
    # input_string = 'RDLv_HATY_13_11_05.ruv'
    m = p.search(input_string) 
    # m.groups() # should be ('2013', '11', '05', '00', '00', None) for 'RDLv_HATY_2013_11_05_0000.ruv'
    if m:
        values = [int(yi) for yi in m.groups() if yi is not None] # [2013, 11, 5, 0, 0]
        # datetime.datetime(*v) requires mininum of year, month, day
        dt = datetime.datetime(*values) # datetime.datetime(2013, 11, 5, 0, 0)
    else:
        dt = None
    return dt

# for testing
if __name__ == '__main__':
    # 
    # datadir = sys.argv[1]
    # patterntype = sys.argv[2]
    # patterntype = 'MeasPattern' 
    # patterntype = 'IdealPattern'
    
    # read in the data
    ifn = os.path.join('.', 'test', 'files', 'codar_raw', \
                   'Radialmetric_HATY_2013_11_05', \
                   'RDLv_HATY_2013_11_05_0000.ruv')
    d, types_str, header, footer = read_lluv_file(ifn)
    # thresholding
    # dall = threshold_qc_all(d, types_str, thresholds=[5.0, 50.0, 5.0])
    # weighting
    xd, xtypes_str = weighted_velocities(d, types_str, 0.0, 'SNR')
    
    # create radialshort data, first generate array then fill it
    rsd, rsdtypes_str = generate_radialshort_array(d, types_str)
    rsd = fill_radialshort_array(rsd, rsdtypes_str, xd, xtypes_str)[0]
    # modify header from radialmetric, based on new radialshort data
    rsdheader = generate_radialshort_header(rsd, rsdtypes_str, header)
    # not modifying the footer at this time
    rsdfooter = footer
    # output the radialshort data specified location
    ofn = os.path.join('.', 'test', 'files', 'test_output.txt')
    write_output(ofn, rsdheader, rsd, rsdfooter)
    
    #
    rsc = get_columns(rsdtypes_str)
    xc = get_columns(xtypes_str)
