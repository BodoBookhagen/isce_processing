#!/usr/bin/env python3
"""
Created on Sat Apr 29 15:06:59 2017

@author: Bodo Bookhagen, May 2017
"""

import isce
import isceobj
from isceobj.Sensor import createSensor
import shelve
import argparse
import os
import argparse
import mroipac
from mroipac.baseline.Baseline import Baseline

class Dummy(object):
    pass

#import isce
#from isceobj.XmlUtil import FastXML as xml

parser = argparse.ArgumentParser(description='Import TerraSAR-X CoSSC to SLC')
parser.add_argument('fname_master', type=str, help='filename of master image (e.g., TSX1_SAR__SSC_BRX2_SM_S_SRA_20150713T095616_20150713T095624/TSX1_SAR__SSC_BRX2_SM_S_SRA_20150713T095616_20150713T095624.xml)')
parser.add_argument('slcname_master', type=str, help='output directory containting SLC (e.g., SLC/TSX_20150713)')
parser.add_argument('fname_slave', type=str, help='filename of slave image (e.g., TDX1_SAR__SSC_BTX1_SM_S_SRA_20150713T095616_20150713T095624/TDX1_SAR__SSC_BTX1_SM_S_SRA_20150713T095616_20150713T095624.xml)')
parser.add_argument('slcname_slave', type=str, help='output directory containting SLC (e.g., SLC/TDX_20150713)')
args = parser.parse_args()


#fname_master='/raid/InSAR/TanDEM-X-QdT/dims_op_oc_dfd2_545348042_1/TDM.SAR.COSSC/1285982_002/TDM1_SAR__COS_BIST_SM_S_SRA_20150713T095616_20150713T095624/TSX1_SAR__SSC_BRX2_SM_S_SRA_20150713T095616_20150713T095624/TSX1_SAR__SSC_BRX2_SM_S_SRA_20150713T095616_20150713T095624.xml'
#slcname_master = '/raid/InSAR/TanDEM-X-QdT/SLC/TSX_20150713'
print('Generating SLC for master: {} '.format(os.path.basename(args.fname_master)))
if not os.path.isdir(args.slcname_master):
    os.mkdir(args.slcname_master)
date = os.path.basename(args.slcname_master)
obj = createSensor('TanDEMX')
obj.xml = args.fname_master
obj.output = os.path.join(args.slcname_master, date+'.slc')
if not os.path.exists(obj.output):
    obj.extractImage()
    obj.frame.getImage().renderHdr()
    obj.extractDoppler()
pickName_master = os.path.join(args.slcname_master, 'data')
if os.path.exists(pickName_master):
    with shelve.open(pickName_master, flag='r') as mdb:
        mFrame = mdb['frame']
else:    
    with shelve.open(pickName_master) as mdb:
        mdb['frame'] = obj.frame
        mFrame = mdb['frame']
mdoppler = mFrame._dopplerVsPixel


#fname_slave='/raid/InSAR/TanDEM-X-QdT/dims_op_oc_dfd2_545348042_1/TDM.SAR.COSSC/1285982_002/TDM1_SAR__COS_BIST_SM_S_SRA_20150713T095616_20150713T095624/TDX1_SAR__SSC_BTX1_SM_S_SRA_20150713T095616_20150713T095624/TDX1_SAR__SSC_BTX1_SM_S_SRA_20150713T095616_20150713T095624.xml'
#slcname_slave = '/raid/InSAR/TanDEM-X-QdT/SLC/TDX_20150713'
print('Generating SLC for slave: {} '.format(os.path.basename(args.fname_slave)))
if not os.path.isdir(args.slcname_slave):
    os.mkdir(args.slcname_slave)
date = os.path.basename(args.slcname_slave)
obj = createSensor('TanDEMX')
obj.xml = args.fname_slave
obj.output = os.path.join(args.slcname_slave, date+'.slc')
if not os.path.exists(obj.output):
    obj.extractImage()
    obj.frame.getImage().renderHdr()
    obj.extractDoppler()
pickName_slave = os.path.join(args.slcname_slave, 'data')
if os.path.exists(pickName_slave):
    with shelve.open(pickName_slave, flag='r') as sdb:
        sFrame = sdb['frame']
else:
    with shelve.open(pickName_slave) as sdb:
        sdb['frame'] = obj.frame
        sFrame = sdb['frame']

### Baseline generation
bObj = Baseline()
bObj.configure()
bObj.wireInputPort(name='masterFrame', object=mFrame)
bObj.wireInputPort(name='slaveFrame', object=sFrame)
bObj.baseline()
print('Baseline at top/bottom: %f %f'%(bObj.pBaselineTop,bObj.pBaselineBottom))
    
mdb.close()
sdb.close()
