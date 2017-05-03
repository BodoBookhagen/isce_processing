# -*- coding: utf-8 -*-

"""
B. Bookhagen, Nov 23, 2015 version 0.1
B. Bookhagen, May, 2017 version 0.11
"""

import subprocess, os, sys, shutil, math, glob, csv, datetime, time
import numpy as np
import xml.etree.ElementTree as ET
import matplotlib.pyplot as plt
from matplotlib.dates import YearLocator, MonthLocator, DateFormatter
import argparse
#import isce
#from isceobj.XmlUtil import FastXML as xml

from osgeo import gdal, gdalnumeric, osr
gdal.UseExceptions()
DEVNULL = open(os.devnull, 'wb')

conncomp_mean = []
conncomp_2use_idx = []
los_mean = []
los_min = []
los_max = []
los2_mean = []
los2_min = []
los2_max = []


parser = argparse.ArgumentParser(description='Process Sentinel1 radar data and generate interferograms (B. Bookhagen, bodo.bookhagen@uni-potsdam.de, v0.11)')
parser.add_argument('indir', help='directory to be processed (e.g., /raid/InSAR/Sentinel1A/NWArg)')
parser.add_argument('baseline', type=int, default=500, help='perpendicular baseline threshold in m')
parser.add_argument('--dem', dest="dem", default = "", help='DEM to be used for processing (e.g., --dem /raid/InSAR/TerraSAR-X/Pocitos/SRTM1/demLat_S23_S26_Lon_W069_W066_f2.dem.wgs84.xml)')
parser.add_argument('--dem_res', type=int, default=30, dest="dem_res", help='DEM resolution: default is 30 (m) for SRTM-X (use 10 m here for the WorldDEM). This is only used when converting TIF files to UTM coordinates.')
parser.add_argument('--roi', dest="roi", default = "", help='region of interest bounding box with S, N, W, E coordinates (include " ", e.g., --roi "[-24,-24.75,-67.25,-66.75]")')
parser.add_argument('--box', dest="box", default = "", help='bounding box with S, N, W, E coordinates (include " ", e.g., --box "[-24,-24.75,-67.25,-66.75]")')
parser.add_argument('--label', dest="label", default = "", help='text string indicating label of current area (e.g., --label "salta_lower_qdt")')
parser.add_argument('--proc_steps', type=int, default=0, dest="proc_steps", help='indicating level of processing (e.g., --proc_steps 0 (default) processes all band combinations that are below baseline threshold, --proc_steps 1 is only baseline generation, --proc_steps 2 will generate baselines and only one (first) ifg with full extent, --proc_steps 3 will generate ifgs using the first (oldest) as master with every other image and then only the next pairs)')
#parser.add_argument('--geoPosting', type=str, default="", dest="geoPosting", help='spatial resolution of geocoded files in lat/long (e.g., --geoPosting 0.0001.')
#parser.add_argument('--posting_m', type=str, default="", dest="posting_m", help='Posting in m.')
parser.add_argument('--geocode_reprocess', type=int, default=0, dest="geocode_reprocess", help='Reprocessing unwrapping with a new geocode bounding box. If geocode bounding box has changed and new geocoding is necessary, set this to 1 (e.g., --geocode_reprocess 1)')
parser.add_argument('--do_not_delete', type=int, default=0, dest="do_not_delete", help='Delete .raw*, rangeOffset.*, resampImage.*, simamp.* after succesfull interferogram formation. Default = 0 to save space. Set this to 1 to keep all files (will require lots of storage, e.g., --do_not_delete 1)')
parser.add_argument('--generate_utm_geotif', type=int, default=0, dest="generate_utm_geotif", help='Generate geotifs for each interferogram pair. Generates geotif and automatically projects to appropriate UTM ZoneX WGS84 coordinate system for the following: filt_topophase.unw.conncomp.geo, filt_topophase.unw.geo, topophase_cor.geo, resampOnlyImage.amp.geo. Default = 0 (no tif files are generated). Set this to 1 to generate geotifs (e.g., --generate_utm_geotif 1)')
parser.add_argument('--orbit_dir', type=str, default="/raid/InSAR/orbits/S1/aux_poeorb", dest="orbit_dir", help='Orbit directory for Sentinel-1A orbits (e.g., --orbit_dir /raid/InSAR/orbits/S1/precise)')
parser.add_argument('--aux_dir', type=str, default="/raid/InSAR/orbits/S1/aux_ins", dest="aux_dir", help='Instrument and calibration auxiliary directory for Sentinel-1A  (e.g., --aux_dir /raid/InSAR/orbits/S1/aux_ins)')
parser.add_argument('--swath', type=str, default="[1,2,3]", dest="swath", help='Swath of Sentinel1 data (1 to 3, e.g., --swath "[1,2,3]" (default) or --swath "[2,3]" for only swaths 2 and 3)')
parser.add_argument('--generate_png', type=int, default=0, dest="generate_png", help='Generate PNGs with mdx for each interferogram pair. Generates merged views with unwrapped topophase, phase, correlation, amplitude. Default = 0 (no PNG files are generated). Set this to 1 to generate png (e.g., --generate_png 1)')

topophase_min = -25
topophase_max = 25

args = parser.parse_args()
sensor_name = 'Sentinel1'

indir = args.indir
PERP_BASELINE_THRESHOLD = args.baseline
print(args)
if args.dem == "":
    dem_file = ""
else:
    dem_file = args.dem

if args.generate_png == 0:
    generate_png = 0
else:
    generate_png = 1

if args.generate_utm_geotif == 0:
    generate_utm_geotif = 0
else:
    generate_utm_geotif = 1

if args.do_not_delete == 0:
    do_not_delete = 0
else:
    do_not_delete = args.do_not_delete

if args.box == "":
    geocode2_textelement = ""
else:
    geocode2_textelement = args.box

if args.roi == "":
    roi_textelement = ""
else:
    roi_textelement = args.roi

if args.proc_steps:
    proc_steps = args.proc_steps
else:
    proc_steps = 0

if args.geocode_reprocess:
    geocode_reprocess = args.geocode_reprocess
else:
    geocode_reprocess = 0

if args.label == "":
    label_txt = ""
else:
    label_txt = args.label

if args.orbit_dir == "":
    orbit_dir = ""
else:
    orbit_dir = args.orbit_dir

if args.aux_dir == "":
    aux_dir = ""
else:
    aux_dir = args.aux_dir

if args.dem_res == "":
    dem_res = 30
else:
    dem_res = args.dem_res

if args.swath != "":
    swath = args.swath
else:
    swath = "[1,2,3]"

print('Processing Sentinel1 data')
print('Indir: ' + indir)
print('Baseline: ' + str(PERP_BASELINE_THRESHOLD))
print('DEM: ' + dem_file)
print('ROI: ' + roi_textelement)
print('BBox: ' + geocode2_textelement)
print('Swaths: ' + swath)
print('Label: ' + label_txt)
print('Processing Steps: ' + str(proc_steps))
print('Geocode_reprocess: ' + str(geocode_reprocess))
print('Do_not_delete: ' + str(do_not_delete))
print('Generate Geotif: ' + str(generate_utm_geotif))
print 'Generate PNG: ' + str(generate_png)
print('Orbit Directory: ' + str(orbit_dir))
print('Auxiliary Directory: ' + str(aux_dir))
ifg_proc_ok = 0 #Flag for ifg processing

if os.path.exists(indir) == False:
    print('Path ' + indir + ' does not exist. Exiting.')
    exit()

log_output_dir = os.path.join(indir, 'log_output')
if os.path.exists(log_output_dir) == False:
    os.mkdir(log_output_dir)

def generate_single_geotif_utm(dir2process, dir2process_merged, date_str, label_txt, baselinet_data, radarwavelength):
    global conncomp_mean
    global conncomp_2use_idx
    global los_mean
    global los_min
    global los_max
    global los2_mean
    global los2_min
    global los2_max

    conncomp_out_fname = os.path.join(dir2process_merged, label_txt + '_conncomp_' + date_str + '.tif')
    phsig_out_fname = os.path.join(dir2process_merged, label_txt + '_phsig_' + date_str + '.tif')
    filttopohase_out_fname = os.path.join(dir2process_merged, label_txt + '_topophase_unw_' + date_str + '.tif')
    filttopohase2stage_out_fname = os.path.join(dir2process_merged, label_txt + '_topophase_2stage_unw_' + date_str + '.tif')
    amp_out_fname = os.path.join(dir2process_merged, label_txt + '_amp_' + date_str + '.tif')
    topophasecor_out_fname = os.path.join(dir2process_merged, label_txt + '_topophase_cor_' + date_str + '.tif')

    date_str = str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))
    if os.path.exists('log') == False:
        os.mkdir('log')
    if len(glob.glob(os.path.join(dir2process_merged, label_txt + '_conncomp_*'  + '.tif'))) > 0:
        print 'Geotif exists for: ' + os.path.join(dir2process_merged, label_txt + '_conncomp_*'  + '.tif')
    else:
        os.chdir(dir2process)
        print 'Converting connected components to geotif: ' + os.path.join(dir2process_merged, 'filt_topophase.unw.conncomp.geo')
#        cmd = ['isce2gis.py', 'vrt', '-i', 'merged/filt_topophase.unw.conncomp.geo']
#        logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#        logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#            subprocess_p.wait()
        cmd = ['gdal_translate', '-b','1', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', 'merged/filt_topophase.unw.conncomp.geo.vrt', conncomp_out_fname]
        logfile_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-mm', '-hist','-stats', conncomp_out_fname]
        gdalinfo_conncomp_logfile_fname = dir2process + '/log/gdalinfo' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        gdalinfo_conncomp_logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(gdalinfo_conncomp_logfile_fname, 'wb') as out, open(gdalinfo_conncomp_logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        with open(gdalinfo_conncomp_logfile_fname) as searchfile:
            for line in searchfile:
                left,sep,right = line.partition('STATISTICS_MEAN=')
                if sep: # True if 'STATISTICS_MEAN' in line
                    conncomp_mean.append(float(right))
                    print 'Mean of connected component: ' + str(float(right))
                    if float(right) > 0.1:
                        conncomp_2use_idx.append(i)

    if len(glob.glob(os.path.join(dir2process_merged, label_txt + '_phsig_*'  + '.tif'))) > 0:
        print 'Geotif exists for: ' + os.path.join(dir2process_merged, label_txt + '_phsig_*'  + '.tif')
    else:
        os.chdir(dir2process)
        date_str = str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))
        print 'Converting phase correlation to geotif: ' + os.path.join(dir2process_merged, 'phsig.cor.geo')
#        cmd = ['isce2gis.py', 'vrt', '-i', 'merged/phsig.cor.geo']
#        logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#        logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#            subprocess_p.wait()
        cmd = ['gdal_translate', '-a_nodata', '0', '-b','1', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', 'merged/phsig.cor.geo.vrt', phsig_out_fname]
        logfile_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-mm', '-hist','-stats', phsig_out_fname]
        gdalinfo_conncomp_logfile_fname = dir2process + '/log/gdalinfo' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        gdalinfo_conncomp_logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(gdalinfo_conncomp_logfile_fname, 'wb') as out, open(gdalinfo_conncomp_logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()

    if len(glob.glob(os.path.join(dir2process_merged, label_txt + '_topophase_cor_*'  + '.tif'))) > 0:
        print 'Geotif exists for: ' + os.path.join(dir2process_merged, label_txt + '_topophase_cor_*'  + '.tif')
    else:
        os.chdir(dir2process)
        date_str = str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))
        print 'Converting topophase correlation to geotif: ' + os.path.join(dir2process_merged, 'topophase.cor.geo')
#        cmd = ['isce2gis.py', 'vrt', '-i', 'merged/phsig.cor.geo']
#        logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#        logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#            subprocess_p.wait()
        cmd = ['gdal_translate', '-a_nodata', '0', '-b','1', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', 'merged/topophase.cor.geo.vrt', topophasecor_out_fname]
        logfile_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-mm', '-hist','-stats', topophasecor_out_fname]
        gdalinfo_conncomp_logfile_fname = dir2process + '/log/gdalinfo' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        gdalinfo_conncomp_logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(gdalinfo_conncomp_logfile_fname, 'wb') as out, open(gdalinfo_conncomp_logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()

    if len(glob.glob(os.path.join(dir2process_merged, label_txt + '_topophase_2stage_unw_*'  + '.tif'))) > 0:
        print 'Geotif exists for: ' + os.path.join(dir2process_merged, label_txt + '_topophase_2stage_unw_*'  + '.tif')
    else:
        os.chdir(dir2process)
        date_str = str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))
        print 'Converting filtered, unwrapped topophase (2 stage) to geotif: ' + os.path.join(dir2process_merged, 'filt_topophase_2stage.unw.geo')
#        cmd = ['isce2gis.py', 'vrt', '-i', 'merged/filt_topophase_2stage.unw.geo']
#        logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#        logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#            subprocess_p.wait()
        cmd = ['gdal_translate', '-a_nodata', '0', '-b','1', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', 'merged/filt_topophase_2stage.unw.geo.vrt', filttopohase2stage_out_fname]
        logfile_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-mm', '-hist','-stats', filttopohase2stage_out_fname]
        gdalinfo_conncomp_logfile_fname = dir2process + '/log/gdalinfo' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        gdalinfo_conncomp_logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(gdalinfo_conncomp_logfile_fname, 'wb') as out, open(gdalinfo_conncomp_logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()

    if len(glob.glob(os.path.join(dir2process_merged, label_txt + '_topophase_unw_*'  + '.tif'))) > 0:
        print 'Geotif exists for: ' + os.path.join(dir2process_merged, label_txt + '_topophase_unw_*'  + '.tif')
    else:
        os.chdir(dir2process)
        date_str = str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))
        print 'Converting filtered, unwrapped topophase to geotif: ' + os.path.join(dir2process_merged, 'filt_topophase.unw.geo')
#        cmd = ['isce2gis.py', 'vrt', '-i', 'merged/filt_topophase.unw.geo']
#        logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#        logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#            subprocess_p.wait()
        cmd = ['gdal_translate', '-a_nodata', '0', '-b','2', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', 'merged/filt_topophase.unw.geo.vrt', filttopohase_out_fname]
        logfile_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-mm', '-hist','-stats', filttopohase_out_fname]
        gdalinfo_conncomp_logfile_fname = dir2process + '/log/gdalinfo' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        gdalinfo_conncomp_logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(gdalinfo_conncomp_logfile_fname, 'wb') as out, open(gdalinfo_conncomp_logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()

    if len(glob.glob(os.path.join(dir2process_merged, label_txt + '_amp_*'  + '.tif'))) > 0:
        print 'Geotif exists for: ' + os.path.join(dir2process_merged, label_txt + '_amp_*'  + '.tif')
    else:
        os.chdir(dir2process)
        date_str = str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))
        print 'Converting amplitude to geotif: ' + os.path.join(dir2process_merged, 'filt_topophase.unw.geo')
#        cmd = ['isce2gis.py', 'vrt', '-i', 'merged/filt_topophase.unw.geo']
#        logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#        logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#            subprocess_p.wait()
        cmd = ['gdal_translate', '-a_nodata', '0', '-b','1', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', 'merged/filt_topophase.unw.geo.vrt', amp_out_fname]
        logfile_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-mm', '-hist','-stats', amp_out_fname]
        gdalinfo_conncomp_logfile_fname = dir2process + '/log/gdalinfo' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        gdalinfo_conncomp_logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(gdalinfo_conncomp_logfile_fname, 'wb') as out, open(gdalinfo_conncomp_logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()

    if len(glob.glob(os.path.join(dir2process_merged, label_txt + '_LOS_*'  + '.tif'))) > 0:
        print 'Geotif exists for: ' + os.path.join(dir2process_merged, label_txt + '_LOS_*'  + '.tif')
    else:
        print 'Converting LOS to geotif: ' + os.path.join(dir2process_merged, 'los.rdr.geo')
#        cmd = ['isce2gis.py', 'vrt', '-i', 'merged/los.rdr.geo']
#        logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#        logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#            subprocess_p.wait()
        los_out_fname = os.path.join(dir2process_merged, label_txt + '_los_' + date_str + '.tif')
        cmd = ['gdal_translate', '-b','1', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', 'merged/los.rdr.geo.vrt', los_out_fname]
        logfile_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-mm', '-hist','-stats', los_out_fname]
        gdalinfo_los_logfile_fname = dir2process + '/log/gdalinfo' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        gdalinfo_los_logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(gdalinfo_los_logfile_fname, 'wb') as out, open(gdalinfo_los_logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        with open(gdalinfo_los_logfile_fname) as searchfile:
            for line in searchfile:
                left,sep,right = line.partition('STATISTICS_MEAN=')
                if sep: # True if 'STATISTICS_MEAN' in line
                    los_mean.append(float(right))
                    print 'Mean of los: ' + str(float(right)) + ', ',
        with open(gdalinfo_los_logfile_fname) as searchfile:
            for line in searchfile:
                left,sep,right = line.partition('STATISTICS_MINIMUM=')
                if sep: # True if 'STATISTICS_MEAN' in line
                    los_min.append(float(right))
                    print 'Min of los: ' + str(float(right)) + ', ',
        with open(gdalinfo_los_logfile_fname) as searchfile:
            for line in searchfile:
                left,sep,right = line.partition('STATISTICS_MAXIMUM=')
                if sep: # True if 'STATISTICS_MEAN' in line
                    los_max.append(float(right))
                    print 'Max of los: ' + str(float(right))

        los2_out_fname = os.path.join(dir2process_merged, label_txt + '_los2_' + date_str + '.tif')
        cmd = ['gdal_translate', '-b','2', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', 'merged/los.rdr.geo.vrt', los2_out_fname]
        logfile_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = dir2process + '/log/gdal_translate_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-mm', '-hist','-stats', los2_out_fname]
        gdalinfo_los_logfile_fname = dir2process + '/log/gdalinfo' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        gdalinfo_los_logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(gdalinfo_los_logfile_fname, 'wb') as out, open(gdalinfo_los_logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        with open(gdalinfo_los_logfile_fname) as searchfile:
            for line in searchfile:
                left,sep,right = line.partition('STATISTICS_MEAN=')
                if sep: # True if 'STATISTICS_MEAN' in line
                    los2_mean.append(float(right))
                    print 'Mean of los2: ' + str(float(right)) + ', ',
        with open(gdalinfo_los_logfile_fname) as searchfile:
            for line in searchfile:
                left,sep,right = line.partition('STATISTICS_MINIMUM=')
                if sep: # True if 'STATISTICS_MEAN' in line
                    los2_min.append(float(right))
                    print 'Min of los2: ' + str(float(right)) + ', ',
        with open(gdalinfo_los_logfile_fname) as searchfile:
            for line in searchfile:
                left,sep,right = line.partition('STATISTICS_MAXIMUM=')
                if sep: # True if 'STATISTICS_MEAN' in line
                    los2_max.append(float(right))
                    print 'Max of los2: ' + str(float(right))


        #radarwavelength = 0.05546576
        deltat_y = baselinet_data[i,2]
        t = gdal.Open(filttopohase2stage_out_fname)
        gt = t.GetGeoTransform()
        cs = t.GetProjection()
        cs_sr = osr.SpatialReference()
        cs_sr.ImportFromWkt(cs)
        del t
        topophase = gdalnumeric.LoadFile(filttopohase2stage_out_fname).astype(float)
        cols = topophase.shape[1]
        rows = topophase.shape[0]
        topophase_m_yr = (topophase * (radarwavelength/4*np.pi)) / float(deltat_y)

        filttopohase_m_yr_out_fname = os.path.join(dir2process_merged, label_txt + '_LOS_deformation_m_yr_' + date_str + '.tif')
        driver = gdal.GetDriverByName('GTiff')
        driver.Register()
        outRaster = driver.Create(filttopohase_m_yr_out_fname, cols, rows, 1, gdal.GDT_Float32)
        outRaster.SetGeoTransform(gt)
        outRaster.SetProjection(cs)
        outband = outRaster.GetRasterBand(1)
        outband.SetMetadataItem('Band', 'LOS Deformation in m/yr')
        outband.SetNoDataValue(0)
        outband.WriteArray(topophase_m_yr,0,0)
        outband.FlushCache()
        del driver, outRaster, topophase_m_yr, topophase

    #Get Zone information from vrt file:
    if (generate_utm_geotif == 1) or (len(glob.glob(os.path.join(dir2process_merged, label_txt + '_phsig_' + date_str + '_UTM*_WGS84.tif'))) == 0 or \
        len(glob.glob(os.path.join(dir2process_merged, label_txt + '_conncomp*' + date_str + '_UTM*_WGS84.tif'))) == 0 or \
        len(glob.glob(os.path.join(dir2process_merged, label_txt + '_topophase_unw_' + date_str + '_UTM*_WGS84.tif'))) == 0):

        if len(glob.glob(os.path.join(dir2process_merged, label_txt + '_phsig_' + date_str + '_UTM*_WGS84.tif'))) == 0:
            cmd = ['isce2gis.py', 'vrt', '-i', 'merged/phsig.cor.geo']
            logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()

        tree = ET.parse(os.path.join(dir2process_merged, 'phsig.cor.geo.vrt'))
        geotransform = tree.find('GeoTransform').text
        Px = float(geotransform.split(',')[0])
        Py = float(geotransform.split(',')[3])
        Zone = math.floor((Px + 180)/6) + 1
        if Px >= 56.0 and Px <= 64.0 and Zone > 3.0 and Zone < 12.0:
            Zone = 32
        Zone = str(int(Zone))
        if Py > 0:
            prj = '+proj=utm +zone=' + Zone + ' +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
            if label_txt <> "":
                phsig_out_fname_utm = label_txt + '_phsig_'+ date_str + '_UTM' + Zone + 'N_WGS84.tif'
                conncomp_out_fname_utm = label_txt + '_conncomp_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                amp_out_fname_utm = label_txt + '_amp_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                topophasecor_out_fname_utm = label_txt + '_topophase_cor_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                topophase_out_fname_utm = label_txt + '_topophase_unw_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                topophase2stage_out_fname_utm = label_txt + '_topophase_2stage_unw_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                topophase_myr_out_fname_utm = label_txt + '_topophase_m_yr_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
            else:
                phsig_out_fname_utm = 'phsig_'+ date_str + '_UTM' + Zone + 'N_WGS84.tif'
                conncomp_out_fname_utm = 'conncomp_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                topophasecor_out_fname_utm = 'topophase_cor_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                topophase_out_fname_utm = 'topophase_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                amp_out_fname_utm = 'amp_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                topophase2stage_out_fname_utm = 'topophase_2stage_unw_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
                topophase_myr_out_fname_utm = 'topophase_m_yr_' + date_str + '_UTM_' + Zone + 'N_WGS84.tif'
        if Py < 0:
            prj = '+proj=utm +zone=' + Zone + ' +south +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
            if label_txt <> "":
                phsig_out_fname_utm = label_txt + '_phsig_'+ date_str + '_UTM' + Zone + 'S_WGS84.tif'
                conncomp_out_fname_utm = label_txt + '_conncomp_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                topophasecor_out_fname_utm = label_txt + '_topophase_cor_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                topophase_out_fname_utm = label_txt + '_topophase_unw_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                amp_out_fname_utm = label_txt + '_amp_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                topophase2stage_out_fname_utm = label_txt + '_topophase_2stage_unw_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                topophase_myr_out_fname_utm = label_txt + '_topophase_m_yr_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
            else:
                phsig_out_fname_utm = 'phsig_'+ date_str + '_UTM' + Zone + 'S_WGS84.tif'
                conncomp_out_fname_utm = 'conncomp_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                topophasecor_out_fname_utm = 'topophase_cor_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                topophase_out_fname_utm = 'topophase_unw_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                amp_out_fname_utm = 'amp_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                topophase_myr_out_fname_utm = 'topophase_m_yr_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'
                topophase2stage_out_fname_utm = label_txt + '_topophase_2stage_unw_' + date_str + '_UTM_' + Zone + 'S_WGS84.tif'


        if os.path.exists(os.path.join(dir2process_merged,topophase_myr_out_fname_utm)) == False:
            cmd = ['gdalwarp', '-srcnodata', '0', '-dstnodata', '0', '-multi', '-tap', '-tr', str(dem_res), str(dem_res), '-t_srs', prj, '-r', 'bilinear', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', filttopohase_m_yr_out_fname, os.path.join(dir2process_merged,topophase_myr_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()
            cmd = ['gdalinfo', '-mm', '-hist', '-stats', os.path.join(dir2process_merged,topophase_myr_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()

        if os.path.exists(os.path.join(dir2process_merged,topophasecor_out_fname_utm)) == False:
            cmd = ['gdalwarp', '-srcnodata', '0', '-dstnodata', '0', '-multi', '-tap', '-tr', str(dem_res), str(dem_res), '-t_srs', prj, '-r', 'bilinear', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', topophasecor_out_fname, os.path.join(dir2process_merged,topophasecor_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()
            cmd = ['gdalinfo', '-mm', '-hist', '-stats', os.path.join(dir2process_merged,topophasecor_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()

        if os.path.exists(os.path.join(dir2process_merged,topophase_out_fname_utm)) == False:
            cmd = ['gdalwarp', '-srcnodata', '0', '-dstnodata', '0', '-multi', '-tap', '-tr', str(dem_res), str(dem_res), '-t_srs', prj, '-r', 'bilinear', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', filttopohase_out_fname, os.path.join(dir2process_merged,topophase_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()
            cmd = ['gdalinfo', '-mm', '-hist', '-stats', os.path.join(dir2process_merged,topophase_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()

        if os.path.exists(os.path.join(dir2process_merged,topophase2stage_out_fname_utm)) == False:
            cmd = ['gdalwarp', '-srcnodata', '0', '-dstnodata', '0', '-multi', '-tap', '-tr', str(dem_res), str(dem_res), '-t_srs', prj, '-r', 'bilinear', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', filttopohase2stage_out_fname, os.path.join(dir2process_merged,topophase2stage_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()
            cmd = ['gdalinfo', '-mm', '-hist', '-stats', os.path.join(dir2process_merged,topophase2stage_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()

        if os.path.exists(os.path.join(dir2process_merged,amp_out_fname_utm)) == False:
            cmd = ['gdalwarp', '-srcnodata', '0', '-dstnodata', '0', '-multi', '-tap', '-tr', str(dem_res), str(dem_res), '-t_srs', prj, '-r', 'bilinear', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', amp_out_fname, os.path.join(dir2process_merged,amp_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()
            cmd = ['gdalinfo', '-mm', '-hist', '-stats', os.path.join(dir2process_merged,amp_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()

        if os.path.exists(os.path.join(dir2process_merged,phsig_out_fname_utm)) == False:
            cmd = ['gdalwarp', '-srcnodata', '0', '-dstnodata', '0', '-multi', '-tap', '-tr', str(dem_res), str(dem_res), '-t_srs', prj, '-r', 'bilinear', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', phsig_out_fname, os.path.join(dir2process_merged,phsig_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()
            cmd = ['gdalinfo', '-mm', '-hist', '-stats', os.path.join(dir2process_merged,phsig_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()

        if os.path.exists(os.path.join(dir2process_merged,conncomp_out_fname_utm)) == False:
            cmd = ['gdalwarp', '-tap', '-tr', str(dem_res), str(dem_res), '-t_srs', prj, '-r', 'near', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', conncomp_out_fname, os.path.join(dir2process_merged,conncomp_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()
            cmd = ['gdalinfo', '-mm', '-hist', '-stats', os.path.join(dir2process_merged,conncomp_out_fname_utm)]
            logfile_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = dir2process + '/log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                subprocess_p.wait()


def generate_single_png(topophase_min, topophase_max, indir, dir2process_merged, date2process, dem_flag):
    print 'Generating PNGs from processed amplitude, coherence, unwrapped phase: ' + date2process
    cmd1a = ['mdx.py', '-P', 'merged/filt_topophase.unw.geo', '-min', str(topophase_min), '-max', str(topophase_max)]
    cmd1b = ['convert', '-despeckle', '-resize', '75%', 'out.ppm', 'filt_topophase_unw_' + date2process + '.png']
    cmd1c = ['rm', 'out.ppm']
    cmd1d = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '128',  '-gravity', 'NorthEast', '-annotate', '+10+10', '%t', 'filt_topophase_unw_' + date2process + '.png']
    logfile_fname = 'log/png_filt_topophase_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    logfile_error_fname = 'log/png_filt_topophase_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
    with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
        subprocess_p = subprocess.Popen(cmd1a, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd1b, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd1c, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd1d, stdout=out, stderr=err)
        subprocess_p.wait()

    cmd2a = ['mdx.py', '-P', 'merged/filt_topophase.unw.conncomp.geo']
    cmd2b = ['convert', '-despeckle', '-resize', '75%', 'out.ppm', 'filt_topophase_unw_conncomp_' + date2process + '.png']
    cmd2c = ['rm', 'out.ppm']
    cmd2d = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '128',  '-gravity', 'NorthEast', '-annotate', '+10+10', '%t', 'filt_topophase_unw_conncomp_' + date2process + '.png']
    logfile_fname = 'log/png_filt_topophase_conncomp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    logfile_error_fname = 'log/png_filt_topophase_conncomp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
    with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
        subprocess_p = subprocess.Popen(cmd2a, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd2b, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd2c, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd2d, stdout=out, stderr=err)
        subprocess_p.wait()

#    cmd = ['/bin/sed', '-i', "s/<value>bil/<value>unw/g", 'merged/filt_topophase_2stage.unw.geo.xml']
#    logfile_fname = 'sed_2stage_unw_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#    logfile_error_fname = 'sed_2stage_unw_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#    with open(os.path.join(log_output_dir, logfile_fname), 'wb') as out, open(os.path.join(log_output_dir,logfile_error_fname), 'wb') as err:
#        subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#        subprocess_p.wait()
#
#    cmd3a = ['mdx.py', '-P', 'merged/filt_topophase_2stage.unw.geo']
#    cmd3b = ['convert', '-despeckle', '-resize', '75%', 'out.ppm', 'filt_topophase_2stage_unw_' + date2process + '.png']
#    cmd3c = ['rm', 'out.ppm']
#    cmd3d = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '128',  '-gravity', 'NorthEast', '-annotate', '+10+10', '%t', 'filt_topophase_unw_2stage_' + date2process + '.png']
#    logfile_fname = 'log/png_filt_topophase_2stage_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#    logfile_error_fname = 'log/png_filt_topophase_2stage_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#    with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#        subprocess_p = subprocess.Popen(cmd3a, stdout=out, stderr=err)
#        subprocess_p.wait()
#        subprocess_p = subprocess.Popen(cmd3b, stdout=out, stderr=err)
#        subprocess_p.wait()
#        subprocess_p = subprocess.Popen(cmd3c, stdout=out, stderr=err)
#        subprocess_p.wait()
#        subprocess_p = subprocess.Popen(cmd3d, stdout=out, stderr=err)
#        subprocess_p.wait()

    cmd4a = ['mdx.py', '-P', 'merged/phsig.cor.geo']
    cmd4b = ['convert', '-despeckle', '-resize', '75%', 'out.ppm', 'phsig_cor_' + date2process + '.png']
    cmd4c = ['rm', 'out.ppm']
    cmd4d = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '128',  '-gravity', 'NorthEast', '-annotate', '+10+10', '%t', 'phsig_cor_' + date2process + '.png']
    logfile_fname = 'log/png_phsig_cor_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    logfile_error_fname = 'log/png_phsig_cor_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
    with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
        subprocess_p = subprocess.Popen(cmd4a, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd4b, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd4c, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd4d, stdout=out, stderr=err)
        subprocess_p.wait()

#use first band for amplitude and second band for topophase
    cmd5a = ['mdx.py', '-P', 'merged/topophase.cor.geo']
    cmd5b = ['convert', '-despeckle', '-resize', '75%', 'out.ppm', 'topophase_cor_' + date2process + '.png']
    cmd5c = ['rm', 'out.ppm']
    cmd5d = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '128',  '-gravity', 'NorthEast', '-annotate', '+10+10', '%t', 'topophase_cor_' + date2process + '.png']
    logfile_fname = 'log/png_topophase_amp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    logfile_error_fname = 'log/png_topophase_amp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
    with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
        subprocess_p = subprocess.Popen(cmd5a, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd5b, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd5c, stdout=out, stderr=err)
        subprocess_p.wait()
        subprocess_p = subprocess.Popen(cmd5d, stdout=out, stderr=err)
        subprocess_p.wait()

    if dem_flag == True:
        cmd6a = ['mdx.py', '-P', 'merged/dem.crop']
        cmd6b = ['convert', '-despeckle', '-resize', '75%', 'out.ppm', 'dem_' + date2process + '.png']
        cmd6c = ['rm', 'out.ppm']
        cmd6d = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '128',  '-gravity', 'NorthEast', '-annotate', '+10+10', '%t', 'dem_' + date2process + '.png']
        logfile_fname = 'log/png_dem_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/png_dem_amp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd6a, stdout=out, stderr=err)
            subprocess_p.wait()
            subprocess_p = subprocess.Popen(cmd6b, stdout=out, stderr=err)
            subprocess_p.wait()
            subprocess_p = subprocess.Popen(cmd6c, stdout=out, stderr=err)
            subprocess_p.wait()
            subprocess_p = subprocess.Popen(cmd6d, stdout=out, stderr=err)
            subprocess_p.wait()

    append_list = glob.glob('*_' + date2process + '.png')
    append_list.sort()
    #print append_list
    png_file_basename = []
    for png_file in append_list:
        png_file_basename.append(os.path.basename(png_file))

    if (len(png_file_basename) == 3):
        cmd6a = ['convert', png_file_basename[0], png_file_basename[1], png_file_basename[2], '+append', 'merged_views_' + date2process + '.png']
        #cmd6b = ['convert', 'merged_views_' + date2process + '.png', 'merged_views_' + date2process  + '.pdf']
        cmd6c = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '256',  '-gravity', 'SouthEast', '-annotate', '+10+10', date2process, 'merged_views_' + date2process + '.png']
        logfile_fname = 'log/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd6a, stdout=out, stderr=err)
            subprocess_p.wait()
#            subprocess_p = subprocess.Popen(cmd6b, stdout=out, stderr=err)
#            subprocess_p.wait()
            subprocess_p = subprocess.Popen(cmd6c, stdout=out, stderr=err)
            subprocess_p.wait()

        cmd7a = ['rm', '-fr', png_file_basename[0], png_file_basename[1], png_file_basename[2]]
        logfile_fname = 'log/png_rm_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/png_rm_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd7a, stdout=out, stderr=err)
            subprocess_p.wait()

    elif (len(png_file_basename) > 4):
        cmd6a = ['convert', png_file_basename[0], png_file_basename[1], png_file_basename[2], png_file_basename[3], png_file_basename[4], '+append', 'merged_views_' + date2process + '.png']
        #cmd6b = ['convert', 'merged_views_' + date2process + '.png', 'merged_views_' + date2process  + '.pdf']
    	cmd6c = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '256',  '-gravity', 'SouthEast', '-annotate', '+10+10', date2process, 'merged_views_' + date2process + '.png']
        logfile_fname = 'log/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd6a, stdout=out, stderr=err)
            subprocess_p.wait()
#            subprocess_p = subprocess.Popen(cmd6b, stdout=out, stderr=err)
#            subprocess_p.wait()
            subprocess_p = subprocess.Popen(cmd6c, stdout=out, stderr=err)
            subprocess_p.wait()

        cmd7a = ['rm', '-fr', png_file_basename[0], png_file_basename[1], png_file_basename[2], png_file_basename[3], png_file_basename[4]]
        logfile_fname = 'log/png_rm_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/png_rm_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd7a, stdout=out, stderr=err)
            subprocess_p.wait()

    elif (len(png_file_basename) == 4):
        cmd6a = ['convert', png_file_basename[0], png_file_basename[1], png_file_basename[2], png_file_basename[3], '+append', 'merged_views_' + date2process + '.png']
        #cmd6b = ['convert', 'merged_views_' + date2process + '.png', 'merged_views_' + date2process  + '.pdf']
    	cmd6c = ['mogrify', '-format', "png", '-font', 'Liberation-Sans', '-fill', 'white', '-undercolor','#00000080', '-pointsize', '256',  '-gravity', 'SouthEast', '-annotate', '+10+10', date2process, 'merged_views_' + date2process + '.png']
        logfile_fname = 'log/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd6a, stdout=out, stderr=err)
            subprocess_p.wait()
#            subprocess_p = subprocess.Popen(cmd6b, stdout=out, stderr=err)
#            subprocess_p.wait()
            subprocess_p = subprocess.Popen(cmd6c, stdout=out, stderr=err)
            subprocess_p.wait()

        cmd7a = ['rm', '-fr', png_file_basename[0], png_file_basename[1], png_file_basename[2], png_file_basename[3]]
        logfile_fname = 'log/png_rm_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/png_rm_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd7a, stdout=out, stderr=err)
            subprocess_p.wait()

def build_xmls(idx, master_slave_string, indir, swath, orbit_dir, aux_dir, Sentinel1_full_zipname, Sentinel1_full_dirname, date, ImgSceneCenterDate, ImgSceneCenterDateTime):
    xmlfile_master = str(date) + '.xml'
    xmldirfile_master = os.path.join(indir, xmlfile_master)
    #output_directory = os.path.join(dirname_full_swath, master_slave_string)
    try:
        idx2 = idx[0]
    except IndexError:
        idx2 = idx
    idx = idx2
    idx2 = None
    Sentinel1_full_zipname_idx = Sentinel1_full_zipname[idx]
    #out_swath_dir = 'output_swath' + str(swath)
    output_directory = os.path.join(Sentinel1_full_dirname[idx], master_slave_string)
#    if os.path.exists(output_directory) == False:
#        os.mkdir(output_directory)
    #output_directory = os.path.join(output_directory, out_swath_dir)
    #if os.path.exists(output_directory) == False:
    #    os.mkdir(output_directory)

    #verify if file exists:
    #if os.path.exists(xmldirfile_master) == False:
    f = open(xmldirfile_master, 'w+')
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    f.write('<component name="master">\n')
    f.write('       <property name="safe">\n')
    f.write('           <value>"%s"</value>\n' % Sentinel1_full_zipname_idx)
    f.write('       </property>\n')
#    f.write('       <property name="swath number">\n')
#    f.write('           <value>%s</value>\n' % swath)
#    f.write('       </property>\n')
    f.write('       <property name="output directory">\n')
    f.write('           <value>"%s"</value>\n' % output_directory)
    f.write('       </property>\n')
    f.write('       <property name="orbit directory">\n')
    f.write('           <value>"%s"</value>\n' % orbit_dir)
    f.write('       </property>\n')
    f.write('       <property name="auxiliary data directory">\n')
    f.write('           <value>"%s"</value>\n' % aux_dir)
    f.write('       </property>\n')
    f.write('</component>\n')
    return output_directory, xmldirfile_master, Sentinel1_full_dirname[idx]

ImgSceneCenterDateTime = []
ImgSceneCenterDate = []
ImgSceneCenterTime = []
Sentinel1_dirname = []
Sentinel1_full_dirname = []
tfname_full_zip_list = []
Sentinel1_zipname = []
Sentinel1_full_zipname = []
Sentinel1_zipname_merged = []
Sentinel1_full_zipname_merged = []

counter = 0
#get list of .zip or .tar.gz files
if len(glob.glob(os.path.join(indir,"S1?_IW_SLC__*.zip"))) > 0:
    tar_filelist = sorted(glob.glob(os.path.join(indir,"S1?_IW_SLC__*.zip")))
#    if len(tar_filelist) == 0 and len(glob.glob(os.path.join(indir,"SO_*.tar.gz"))) > 0:
#        tar_filelist = sorted(glob.glob(os.path.join(indir,"SO_*.tar.gz")))
    for file in tar_filelist:
        fname = os.path.basename(file)
        fname_out = fname.split('.')[0]
#        print('\nProcessing: ' + fname),
#        if os.path.exists(fname_out + '.SAFE') == False:
#            print('... unzipping '),
#            os.chdir(os.path.dirname(file))
#            cmd = ['unzip', '-u', fname]
#            wait = subprocess.Popen(cmd)
#            wait.wait()
#        else:
#            print('... exists'),
        #now extract date and timing
        tfname_zip = os.path.basename(os.path.join(os.path.dirname(file), fname_out + '.zip'))
        tfname_full_zip = os.path.join(os.path.dirname(file), fname_out + '.zip')
        tfname = os.path.basename(os.path.join(os.path.dirname(file), fname_out + '.SAFE'))
        tfname_full = os.path.join(os.path.dirname(file), fname_out + '.SAFE')
        fname_date = tfname[17:25]
        fname_time = tfname[26:32]
        tfname_full_zip_list.append(tfname_full_zip)
#        if fname_date in ImgSceneCenterDate:
#            ImgSceneCenterDateTime2merge.append(ImgSceneCenterDateTime[-1])
#            tfname_zip_list2merge.append('"' + tfname_full_zip_list[-1]'", "' + tfname_full_zip + '"')

        if fname_date not in ImgSceneCenterDate:
            ImgSceneCenterDateTime.append(datetime.datetime(int(fname_date[0:4]), int(fname_date[4:6]), int(fname_date[6:8]), int(fname_time[0:2]), int(fname_time[2:4]), int(fname_time[4:6])))
            ImgSceneCenterDate.append(fname_date)
            ImgSceneCenterTime.append(fname_time)
            Sentinel1_dirname.append(tfname)
            Sentinel1_full_dirname.append(tfname_full)
            Sentinel1_zipname.append(tfname_zip)
            Sentinel1_full_zipname.append(tfname_full_zip)
            counter = counter + 1
        elif fname_date in ImgSceneCenterDate:
            #file should be combined with existing SAFE/zip file. Because files are sorted, it is the previous file
            Sentinel1_zipname_merged.append([Sentinel1_zipname[-1], tfname_zip])
            Sentinel1_zipname.pop()
            Sentinel1_zipname.append(Sentinel1_zipname_merged[-1])
            Sentinel1_full_zipname_merged.append([Sentinel1_full_zipname[-1], tfname_zip])
            Sentinel1_full_zipname.pop()
            Sentinel1_full_zipname.append(Sentinel1_full_zipname_merged[-1])

elif len(glob.glob(os.path.join(indir,"S1?_IW_SLC__*.SAFE"))) > 0:
    SAFE_filelist = sorted(glob.glob(os.path.join(indir,"S1?_IW_SLC__*.SAFE")))
    for file in SAFE_filelist:
        fname = os.path.basename(file)
        print('\nProcessing: ' + fname),
        #now extract date and timing
        tfname = fname
        tfname_full = file
        fname_date = tfname[17:25]
        fname_time = tfname[26:32]
        ImgSceneCenterDateTime.append(datetime.datetime(int(fname_date[0:4]), int(fname_date[4:6]), int(fname_date[6:8]), int(fname_time[0:2]), int(fname_time[2:4]), int(fname_time[4:6])))
        ImgSceneCenterDate.append(fname_date)
        ImgSceneCenterTime.append(fname_time)
        Sentinel1_dirname.append(tfname)
        Sentinel1_full_dirname.append(tfname_full)
        counter = counter + 1
indir_path = indir

print('\nProcessed ' + str(counter) + ' files.')

#Analyzing files and generating xml file for calculating pairs
baseline_results = []
baseline_results_lt_threshold = []
baseline_results_lt_threshold_conncomp_los = []
ImgSceneCenterDate_int = np.array(map(int, ImgSceneCenterDate))
ImgSceneCenterDate_unique = np.unique(ImgSceneCenterDate_int)
for date in ImgSceneCenterDate_unique:
    idx = np.where(ImgSceneCenterDate_int == date)
    idx = idx[0]

    #now iterate through that index and generate xml files
    #same indices indicate same days
    if len(idx) > 1:
        idx = idx[0]
    [output_master_directory, xmldirfile_master, Sentinel1A_full_master_dirname] = build_xmls(idx, 'master', indir, swath, orbit_dir, aux_dir, Sentinel1_full_zipname, Sentinel1_full_dirname, date, ImgSceneCenterDate, ImgSceneCenterDateTime)
    try:
        idx2 = idx[0]
    except IndexError:
        idx2 = idx
    idx = idx2
    idx2 = None

    #generate pairs, starting with first data
    #only use pairs that have same number of images (i.e. are on the same row/path)
    if date == ImgSceneCenterDate_unique[0]:
        #first date, create slave list
        date_list = np.copy(ImgSceneCenterDate_unique)
        idx2remove = np.where(date_list == date)
        date_list = np.delete(date_list, idx2remove)
        date_list_save = np.copy(date_list)
    else:
        #for all other times when date_list already exists
        date_list = np.copy(date_list_save)
        idx2remove = np.where(date_list == date)
        date_list = np.delete(date_list, idx2remove)
        date_list_save = np.copy(date_list)

    for cdate in date_list:
        dirname = str(date) + '_' + str(cdate)
        print '\nProcessing ' + str(date) + ' - ', str(cdate)
        dirname_full = os.path.join(indir, dirname)
        if os.path.exists(dirname_full) == False:
            os.mkdir(dirname_full)
        dirname_full_swath = os.path.join(dirname_full)
#        dirname_full_swath = os.path.join(dirname_full, 'swath'+str(swath))
#        if os.path.exists(dirname_full_swath) == False:
#            os.mkdir(dirname_full_swath)
        cidx = np.where(ImgSceneCenterDate_int == cdate)
        cidx = cidx[0]
        if cidx.size > 1:
            cidx = cidx[0]
        try:
            cidx2 = cidx[0]
        except IndexError:
            cidx2 = cidx
        cidx = cidx2
        cidx2 = None
        #make sure that only the same orbits are combined

        #now iterate through that index and generate xml files
        #same indices indicate same days
        [output_slave_directory, xmldirfile_slave, Sentinel1A_full_slave_dirname] = build_xmls(cidx, 'slave', indir, swath, orbit_dir, aux_dir, Sentinel1_full_zipname, Sentinel1_full_dirname, cdate, ImgSceneCenterDate, ImgSceneCenterDateTime)

        #now generate controlling xml file
        topsApp_fname = dirname + '.xml'
        topsApp_fname_full = os.path.join(dirname_full_swath, topsApp_fname)

        f = open(topsApp_fname_full, 'w+')
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<topsApp>\n')
        f.write('   <component name="topsinsar">\n')
        f.write('       <property name="Sensor Name">\n')
        f.write('           <value>SENTINEL1</value>\n')
        f.write('       </property>\n')
        f.write('   <component name="master">\n')
        f.write('       <catalog>%s</catalog>\n' % xmldirfile_master)
        f.write('   </component>\n')
        f.write('   <component name="slave">\n')
        f.write('       <catalog>%s</catalog>\n' % xmldirfile_slave)
        f.write('   </component>\n')
        #GEO_POSTING Output posting for geocoded images in degrees (latitude = longitude)
        #if geoPosting:
	    #    f.write('      <property name="geoPosting"><value>%f</value></property>\n' % geoPosting)
        #f.write('      <property name="posting"><value>%d</value></property>\n' % posting_m)
        if roi_textelement:
            f.write('      <property name="swaths">%s</property>\n' % swath)
        f.write('      <property name="esdcoherencethreshold"><value>0.8</value></property>\n')
        f.write('      <property name="do unwrap"><value>True</value></property>\n')
        f.write('      <property name="unwrapper name">snaphu_mcf</property>\n')
        f.write('      <property name="do unwrap 2 stage"><value>True</value></property>\n')
        f.write('      <property name="unwrapper 2 stage name">MCF</property>\n')
        if dem_file:
            f.write('      <property name="dem file name">%s</property>\n' % dem_file)
#        #f.write('      <property name="filter strength">0.4</property>\n')
        if roi_textelement:
            f.write('      <property name="region of interest"><value>"%s"</value></property>\n' % roi_textelement)
        if geocode2_textelement:
            f.write('      <property name="geocode bounding box"><value>"%s"</value></property>\n' % geocode2_textelement)
            f.write("      <property name='geocode list'>['merged/filt_topophase_2stage.unw', 'merged/filt_topophase.unw.conncomp', 'merged/topophase.cor', 'merged/filt_topophase.flat', 'merged/filt_topophase.unw', 'merged/phsig.cor', 'merged/los.rdr']</property>\n")
        f.write('      <property name="usevirtualfiles"><value>True</value></property>\n')
        f.write('</component>\n')
        f.write('</topsApp>\n')
        f.close()
        if dem_file:
            #link to dem_file
            #print 'dem_file: ' + dem_file
            if dem_file.endswith('.xml') ==  False:
                dem_file_xml_fname = dem_file + '.xml'
                dem_file_vrt_fname = dem_file + '.vrt'
            else:
                dem_file_xml_fname = dem_file
            dem_file_fname = dem_file_xml_fname[0:-4]
            dem_file_vrt_fname = dem_file_xml_fname[0:-4] + '.vrt'

            dst = dirname_full_swath
            #print 'dst: ' + dst + '\nsymfile: ' + os.path.join(dst, os.path.basename(dem_file_xml_fname))+ '\ndem_file: ' + dem_file
            if os.path.exists(os.path.join(dst, os.path.basename(dem_file_xml_fname))) == False:
                os.symlink(dem_file_xml_fname, os.path.join(dst, os.path.basename(dem_file_xml_fname)))
            if os.path.exists(os.path.join(dst, os.path.basename(dem_file_fname))) == False:
                os.symlink(dem_file_fname, os.path.join(dst, os.path.basename(dem_file_fname)))
            if os.path.exists(os.path.join(dst, os.path.basename(dem_file_vrt_fname))) == False:
                os.symlink(dem_file_vrt_fname, os.path.join(dst, os.path.basename(dem_file_vrt_fname)))

        if proc_steps >= 0:
            #now call topsApp.py to determine baseline for this interferogram
            if os.path.exists(os.path.join(dirname_full_swath,  'log')) == False:
                os.mkdir(os.path.join(dirname_full_swath, 'log'))
            perp_baseline = np.nan
            perp_baseline_bottom = np.nan
            perp_baseline_top = np.nan

            origWD = os.getcwd() # remember our original working directory
            if os.path.exists(os.path.join(dirname_full_swath, 'isce.log')) == False:
                #only run for files that don't exist yet
                cmd = ['topsApp.py', '--steps', '--end=computeBaselines', topsApp_fname_full]
                print('Compute baselines: ' + ' '.join(cmd))
                os.chdir(dirname_full_swath)
                if os.path.exists('log') == False:
                    os.mkdir('log')
                logfile_fname = 'log/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                logfile_error_fname = 'log/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                    subprocess_p.wait()
            if 'Bperp' in open(os.path.join(dirname_full_swath, 'isce.log')).read():
                searchfile = open(os.path.join(dirname_full_swath, 'isce.log'), "r")
                perp_baseline_top_list = []
                perp_baseline_bottom_list = []
                for line in searchfile:
                    if "Bperp at midrange for first common burst" in line:
                        perp_baseline_top = float(line.split(' = ')[-1])
                        perp_baseline_top_list.append(perp_baseline_top)
                searchfile.seek(0)
                for line in searchfile:
                    if "Bperp at midrange for last common burst" in line:
                        perp_baseline_bottom = float(line.split(' = ')[-1])
                        perp_baseline_bottom_list.append(perp_baseline_bottom)
                searchfile.close()
                perp_baseline_top = np.mean(perp_baseline_top_list)
                perp_baseline_bottom = np.mean(perp_baseline_bottom_list)
            if np.isnan(perp_baseline_bottom):
                #no perp_baseline, no baseline computed
                logfile_error_fname = max(glob.iglob(os.path.join(dirname_full_swath,'log/topsApp_*_err.txt')), key=os.path.getctime)
                if 'Exception: No suitable orbit file found.' in open(os.path.join(dirname_full_swath, logfile_error_fname)).read():
                    #precise orbts are not here
                    print 'Precise orbits for ' + topsApp_fname_full + ' is missing'
                    #write xml file to list
                    no_precise_orbits_fn =  'list_of_missing_precise_orbits_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                    no_precise_orbits_fn_fp =  os.path.join(indir, no_precise_orbits_fn)
                    f = open(no_precise_orbits_fn_fp, 'a+')
                    f.write('%s\t: %s\n' %(datetime.datetime.now().strftime('%Y%b%d_%H%M%S'), topsApp_fname_full))
                    f.close()
                if 'Exception: Could not determine a suitable burst offset' in open(os.path.join(dirname_full_swath, logfile_error_fname)).read():
                    print 'Could not determine burst offset for ' + topsApp_fname_full
                    #write xml file to list
                    if 'no_burst_offset_fn' not in locals():
                        # myVar exists.
                        no_burst_offset_fn =  'list_of_burst_offset_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                        no_burst_offset_fn_fp =  os.path.join(indir, no_burst_offset_fn)
                    f = open(no_burst_offset_fn_fp, 'a+')
                    f.write('%s\t: %s\n' %(datetime.datetime.now().strftime('%Y%b%d_%H%M%S'), topsApp_fname_full))
                    f.close()

    #        if os.path.exists(os.path.join(dirname_full_swath, output_master_directory)) == False or os.path.exists(os.path.join(dirname_full_swath, output_slave_directory)) == False:
    #            if 'baseline.Bperp' in open(os.path.join(dirname_full_swath, 'isce.log')).read():
    #                searchfile = open(os.path.join(dirname_full_swath, 'isce.log'), "r")
    #                for line in searchfile:
    #                    if "baseline.Bperp at midrange for first common burst" in line:
    #                        perp_baseline_top = float(line.split(' = ')[-1])
    #                        break
    #                for line in searchfile:
    #                    if "baseline.Bperp at midrange for last common burst" in line:
    #                        perp_baseline_bottom = float(line.split(' = ')[-1])
    #                        break
    #                searchfile.close()
    #            else:
    #                cmd = ['topsApp.py', '--steps', '--end=computeBaselines', topsApp_fname_full]
    #                print('Re-Running: ' + ' '.join(cmd))
    #                os.chdir(dirname_full_swath)
    #                logfile_fname = 'log/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    #                logfile_error_fname = 'log/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
    #                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
    #                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
    #                    subprocess_p.wait()

            #extract perpendicular baseline from file insarProc.xml
            #filestats = os.stat(os.path.join(dirname_full_swath, 'insarProc.xml'))
            try:
                perp_baseline_bottom
            except NameError:
                print('No perpendicular baseline found. Break.')
                perp_baseline = np.nan
                perp_baseline_bottom = np.nan
                perp_baseline_top = np.nan
                break
            if perp_baseline_bottom != 0 and np.isnan(perp_baseline_bottom) == False:
                #insarProc.xml contains sufficient data
                #os.chdir(dirname_full_swath)
                #tree = ET.parse(os.path.join(dirname_full_swath, 'insarProc.xml'))
                #perp_baseline_top = float(tree.find('baseline/perp_baseline_top').text)
                #perp_baseline_bottom = float(tree.find('baseline/perp_baseline_bottom').text)
                perp_baseline = np.mean([perp_baseline_top, perp_baseline_bottom])
                print('Perpendicular baseline (m): ' + str(perp_baseline))
                #os.chdir(origWD) #change back to original directory
                #store relevant data
                date_dt = datetime.datetime(int(str(date)[0:4]), int(str(date)[4:6]), int(str(date)[6:8]), 0, 0)
                cdate_dt = datetime.datetime(int(str(cdate)[0:4]), int(str(cdate)[4:6]), int(str(cdate)[6:8]), 0, 0)
                deltadate = cdate_dt - date_dt
                deltadate_yr = deltadate.total_seconds()/(365*24*60*60)
                #print([date, cdate, deltadate_yr, perp_baseline, len(idx), Sentinel1_dirname[idx], Sentinel1_dirname[cidx]])
                if idx.shape == ():
                    baseline_results.append([date, cdate, deltadate_yr, perp_baseline, idx+1, Sentinel1_dirname[idx], Sentinel1_dirname[cidx]])
                else:
                    baseline_results.append([date, cdate, deltadate_yr, perp_baseline, np.size(idx), Sentinel1_dirname[idx], Sentinel1_dirname[cidx]])
                if abs(perp_baseline) > PERP_BASELINE_THRESHOLD:
                    #remove files from subdir to save storage
                    files2remove = os.path.join(dirname_full_swath, str(date))
                    files2remove = files2remove + '.raw*'
                    files2remove=glob.glob(files2remove)
                    for i in files2remove:
                        os.remove(i)
                    files2remove = os.path.join(dirname_full_swath, str(date))
                    files2remove = files2remove + '.iq*'
                    files2remove=glob.glob(files2remove)
                    for i in files2remove:
                        os.remove(i)
                    files2remove = os.path.join(dirname_full_swath, str(cdate))
                    files2remove = files2remove + '.raw*'
                    files2remove=glob.glob(files2remove)
                    for i in files2remove:
                        os.remove(i)
                    files2remove = os.path.join(dirname_full_swath, str(cdate))
                    files2remove = files2remove + '.iq*'
                    files2remove=glob.glob(files2remove)
                    for i in files2remove:
                        os.remove(i)
                    if os.path.exists(os.path.join(dirname_full_swath,'PICKLE')):
                        shutil.rmtree(os.path.join(dirname_full_swath,'PICKLE'))
                else:
                    if idx.shape == ():
                        baseline_results_lt_threshold.append([date, cdate, deltadate_yr, perp_baseline, 2,  Sentinel1_dirname[idx], Sentinel1_dirname[cidx]])
                        baseline_results_lt_threshold_conncomp_los.append([date, cdate, deltadate_yr, perp_baseline, 2,  Sentinel1_dirname[idx], Sentinel1_dirname[cidx]])
                    else:
                        baseline_results_lt_threshold.append([date, cdate, deltadate_yr, perp_baseline, 1,  Sentinel1_dirname[idx], Sentinel1_dirname[cidx]])
                        baseline_results_lt_threshold_conncomp_los.append([date, cdate, deltadate_yr, perp_baseline, 1,  Sentinel1_dirname[idx], Sentinel1_dirname[cidx]])
            else:
                #insarProc too small
                baseline_results.append([date, cdate, -9999, -9999, np.size(idx), -9999, -9999])

if proc_steps == -1:
    print 'Finished generating xml files. Exiting'
    sys.exit()

#write all baselines
baseline_results_csv = os.path.join(indir_path, label_txt + '_baseline_results.csv')
with open(baseline_results_csv, 'wb') as myfile:
    wr = csv.writer(myfile, delimiter=',', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    wr.writerow(['Date1', 'Date2', 'DeltaDate_yr', 'Perp_baseline', 'Nr_of_scenes', 'Scene1', 'Scene2'])
    for item in baseline_results:
        wr.writerow([item[0], item[1], item[2], item[3], item[4], item[5], item[6]])

#write only baselines with perpendicular baseline < THRESHOLD
baseline_fname = label_txt + '_baseline_results_lt_' + str(PERP_BASELINE_THRESHOLD) + '.csv'
baseline_results_lt_threshold_csv = os.path.join(indir_path, baseline_fname)
with open(baseline_results_lt_threshold_csv, 'wb') as myfile:
    wr = csv.writer(myfile, delimiter=',', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    wr.writerow(['Date1', 'Date2', 'DeltaDate_yr', 'Perp_baseline', 'Nr_of_scenes', 'Scene1', 'Scene2'])
    for item in baseline_results_lt_threshold:
        wr.writerow([item[0], item[1], item[2], item[3], item[4], item[5], item[6]])

#write ifg.list for GiANT processing, only baselines with perpendicular baseline < THRESHOLD
ifg_fname = label_txt + '_ifg_all.list'
ifg_fname = os.path.join(indir_path, ifg_fname)
with open(ifg_fname, 'wb') as myfile:
    wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
    #wr.writerow(['Masterdate', 'Slavedate', 'Bperp_in_m', 'Sensor'])
    for item in baseline_results_lt_threshold:
        wr.writerow([item[0], item[1], format(item[3], '+07.2f'), sensor_name])

baselinet_data = np.genfromtxt(baseline_results_lt_threshold_csv, delimiter=',', skip_header=1, usecols = (0, 1, 2, 3, 4))
if baselinet_data.size > 5:
    date_dt = []
    for bdate in baselinet_data[:,0]:
        date_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))
    cdate_dt = []
    for bdate in baselinet_data[:,1]:
        cdate_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))
if baselinet_data.size <= 5:
    date_dt = []
    bdate = baselinet_data[0]
    date_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))
    cdate_dt = []
    bdate = baselinet_data[1]
    cdate_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))

#generate a list of dates with the first image as a master and then only pairs following:
#date1-date2, date1-date3, date1-date4, date2-date3, date3-date4
if proc_steps == 3:
    baselinet_data = np.genfromtxt(baseline_results_lt_threshold_csv, delimiter=',', skip_header=1, usecols = (0, 1, 2, 3, 4))
    first_date_unique = np.unique(baselinet_data[:,0])
    len_counter = len(first_date_unique)
    iter_counter = 0
    baselinet_data_proc3 = np.empty(np.size(baselinet_data))
    for i in first_date_unique:
        if iter_counter == 0:
            #get all datecombinations from first date
            foo = baselinet_data[baselinet_data[:,0]==i]
            baselinet_data_proc3 = foo
            foo = None
        else:
            foo = baselinet_data[baselinet_data[:,0]==i]
            baselinet_data_proc3 = np.append(baselinet_data_proc3, [foo[0]], axis=0)
            foo = None
        iter_counter = iter_counter + 1

    baselinet_data = baselinet_data_proc3
    if baselinet_data.size > 5:
        date_dt = []
        for bdate in baselinet_data[:,0]:
            date_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))
        cdate_dt = []
        for bdate in baselinet_data[:,1]:
            cdate_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))
    if baselinet_data.size <= 5:
        date_dt = []
        bdate = baselinet_data[0]
        date_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))
        cdate_dt = []
        bdate = baselinet_data[1]
        cdate_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))

    #proc_step3: write only baselines with perpendicular baseline < THRESHOLD
    baseline_fname = label_txt + '_ifg_lt_' + str(PERP_BASELINE_THRESHOLD) + '_procstep3.list'
    baseline_results_lt_threshold_csv = os.path.join(indir_path, baseline_fname)
    with open(baseline_results_lt_threshold_csv, 'wb') as myfile:
        wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        #wr.writerow(['Masterdate', 'Slavedate', 'Bperp_in_m', 'Sensor'])
        for item in baselinet_data:
            wr.writerow([format(item[0],'8.0f'), format(item[1], '8.0f'), format(item[3], '+07.2f'), sensor_name])


baselinea_data = np.genfromtxt(baseline_results_csv, delimiter=',', skip_header=1, usecols = (0, 1, 2, 3, 4))
adate_dt = []
for bdate in baselinea_data[:,0]:
    adate_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))
acdate_dt = []
for bdate in baselinea_data[:,1]:
    acdate_dt.append(datetime.datetime(int(str(bdate)[0:4]), int(str(bdate)[4:6]), int(str(bdate)[6:8]), 0, 0))

if proc_steps == 0 or proc_steps > 2:
    #make plot of dates and baselines
    print 'Creating baseline figures...',
    figure_fn_pdf = label_txt + '_baselines.pdf'
    figure_fn_jpg = label_txt + '_baselines.jpg'
    if os.path.exists(os.path.join(indir_path, figure_fn_pdf)):
        print 'already exists.'
    else:
        #Plot 1
        plt.figure(num=1, figsize=(11.69,8.27))
        ax1 = plt.subplot(221)
        plt.ylim([np.divide(np.float(PERP_BASELINE_THRESHOLD*-1), 1000),np.divide(np.float(PERP_BASELINE_THRESHOLD),1000)])
        plt.xlim([datetime.datetime(min(date_dt).year,1,1,0,0), datetime.datetime(max(date_dt).year+1,1,1,0,0)])
        plt.plot(date_dt,np.divide(baselinet_data[:,3], 1000), 'bo')
        plt.grid()
        title_string = indir_path.split('/')[-1] + ': Baseline plot for threshold baselines'
        plt.title(title_string)
        plt.xlabel('Date 1', fontsize = 14)
        plt.ylabel('baseline (km)', fontsize = 14)
        # format the ticks
        years = YearLocator()   # every year
        months = MonthLocator()  # every month
        yearsFmt = DateFormatter('%Y')
        ax1.xaxis.set_major_locator(years)
        ax1.xaxis.set_major_formatter(yearsFmt)
        ax1.xaxis.set_minor_locator(months)
        ax1.autoscale_view()
        #Plot 2
        ax2 = plt.subplot(222)
        plt.xlim([datetime.datetime(min(date_dt).year,1,1,0,0), datetime.datetime(max(date_dt).year+1,1,1,0,0)])
        plt.plot(adate_dt,np.divide(baselinea_data[:,3],1000), 'bo')
        plt.grid()
        title_string = indir_path.split('/')[-1] + ': Baseline plot for all baselines'
        plt.title(title_string)
        plt.xlabel('Date 1', fontsize = 14)
        plt.ylabel('baseline (km)', fontsize = 14)
        # format the ticks
        years = YearLocator()   # every year
        months = MonthLocator()  # every month
        yearsFmt = DateFormatter('%Y')
        ax2.xaxis.set_major_locator(years)
        ax2.xaxis.set_major_formatter(yearsFmt)
        ax2.xaxis.set_minor_locator(months)
        ax2.autoscale_view()
        #Plot 3
        ax3 = plt.subplot(223)
        plt.xlim([datetime.datetime(min(date_dt).year,1,1,0,0), datetime.datetime(max(date_dt).year+1,1,1,0,0)])
        plt.plot(date_dt,baselinet_data[:,2], 'bo')
        plt.grid()
        title_string = indir_path.split('/')[-1] + ': Delta T plot for baselines < ' + str(PERP_BASELINE_THRESHOLD) + ' m'
        plt.title(title_string)
        plt.xlabel('Date 1', fontsize = 14)
        plt.ylabel('Delta T (y)', fontsize = 14)
        # format the ticks
        years = YearLocator()   # every year
        months = MonthLocator()  # every month
        yearsFmt = DateFormatter('%Y')
        ax3.xaxis.set_major_locator(years)
        ax3.xaxis.set_major_formatter(yearsFmt)
        ax3.xaxis.set_minor_locator(months)
        ax3.autoscale_view()
        plt.savefig(os.path.join(indir_path, figure_fn_pdf), bbox_inches='tight', format='pdf')
        plt.savefig(os.path.join(indir_path, figure_fn_jpg), bbox_inches='tight')
    print '\n'

#Now, create interferograms for all pairs with baseline < PERP_BASELINE_THRESHOLD
if proc_steps == 1:
    sys.exit(0)

### THIS IS ONLY GENERATING ONE INTERFEROGRAM
if proc_steps == 2:
    #generate one interferogram from the first of the list
    origWD = os.getcwd() # remember original working directory
    i = 0
    dir2process = str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))
    date_str = dir2process
    xml2process = dir2process + '.xml'
    dir2process_full = os.path.join(indir_path, dir2process)
    dir2process_merged = os.path.join(dir2process_full, 'merged')
    xml2process = os.path.join(dir2process, xml2process)
    print '\n### Generating single interferogram for: ' + dir2process
    os.chdir(dir2process_full)
    if os.path.exists(os.path.join(dir2process_merged, 'filt_topophase.unw.geo')):
        print 'Unwrapped topophase already exists: ' + os.path.join(dir2process_merged, 'filt_topophase.unw.geo')
    else:
        cmd = ['topsApp.py', '--steps', xml2process]
        print '\nRunning ' + str(i+1) + ' of 1: ' + ' '.join(cmd)
        start_t = time.time()
        logfile_fname = 'log/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        end_t = time.time()
        print 'Duration: ' + str(round((end_t-start_t)/60., 2)) + ' minutes or ' + str(round((end_t-start_t)/60./60., 2)) + ' hours'
    date2process = date_str

    if generate_png == 1:
        if os.path.exists('log') == False:
            os.mkdir('log')
        if len(glob.glob(os.path.join(indir,os.path.join(dir2process, 'merged_views_' + date2process + '.png')))) > 0:
            print 'PNG exists for: ' + os.path.join(dir2process, 'merged_views_' + date2process + '.png')
        else:
            generate_single_png(topophase_min, topophase_max, indir, dir2process_merged, date2process, True)

    if generate_utm_geotif == 1:
        if os.path.exists('log') == False:
            os.mkdir('log')
        if len(glob.glob(os.path.join(indir,os.path.join(dir2process, 'merged/*' + date2process + '_UTM*_WGS84.tif')))) > 0:
            print 'Geotifs exists for: ' + date2process
        else:
            radarwavelength = 0.05546576
            generate_single_geotif_utm(dir2process, dir2process_merged, date2process, label_txt, baselinet_data, radarwavelength)
    os.chdir(origWD)


###THIS IS THE USUAL PROCESSING STEP
if proc_steps == 0 or proc_steps == 3:
    #This will prepare files for GiANT processing
    print 'Preparing files for GiANT'
    print 'Generating InSAR pairs with baseline < ' + str(PERP_BASELINE_THRESHOLD) + ' m'
    print 'Generating n = ' + str(len(date_dt)) + ' pairs'
    origWD = os.getcwd() # remember original working directory
    if proc_steps == 3:
        date_dt
    for i in range(len(date_dt)):
        dir2process_noswath = str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))
        date_str = dir2process_noswath
        print '\n###Processing ' + str(i+1) + ' of ' + str(len(date_dt)) + ': ' + dir2process_noswath
        if os.path.exists(os.path.join(indir_path, 'dates_to_exclude.lst')):
            if date_str in open(os.path.join(indir_path, 'dates_to_exclude.lst')).read():
                print 'Continuing to next. ' + dir2process_noswath + ' is in file: dates_to_exlude.lst'
                continue
        xml2process = dir2process_noswath + '.xml'
        dir2process = os.path.join(indir_path, dir2process_noswath)
        dir2process_merged = os.path.join(dir2process, 'merged')
        xml2process = os.path.join(dir2process, xml2process)
        if os.path.exists(xml2process) == True:
            if os.path.exists(os.path.join(dir2process_merged, 'filt_topophase_2stage.unw')) == True or os.path.exists(os.path.join(dir2process_merged, 'filt_topophase.unw')) == True:
                if os.path.exists(os.path.join(dir2process_merged, 'filt_topophase_2stage.unw')) == True:
                    print 'Unwrapped topophases already exists: ' + os.path.join(dir2process_merged, 'filt_topophase_2stage.unw')
                    ifg_proc_ok = 1
                if os.path.exists(os.path.join(dir2process_merged, 'filt_topophase.unw')) == True:
                    print 'Unwrapped topophases already exists: ' + os.path.join(dir2process_merged, 'filt_topophase.unw')
                    ifg_proc_ok = 1
                #print 'xmlprocess: ' + xml2process
                if 'geocode bounding box' not in open(xml2process).read():
                    #geocode bounding box does not exist
                    tree = ET.parse(xml2process)
                    root = tree.getroot()
                    insar = root.find('component')
                    if geocode2_textelement:
                        geocode = ET.SubElement(insar, 'property', {'name': "geocode bounding box"})
                        geocode2 = ET.SubElement(geocode, 'value')
                        geocode2.text = '"' + geocode2_textelement + '"'
                        #geocodelist = ET.SubElement(insar, 'property', {'name': "geocode list"})
                        #geocodelist.text = "['merged/filt_topophase.unw','merged/filt_topophase.unw.conncomp', 'merged/phsig.cor', 'merged/los.rdr']"
                        tree.write(xml2process)
                if 'geocode bounding box' in open(xml2process).read() and geocode_reprocess == 1:
                    #geocode bounding box does exist, replace
                    tree = ET.parse(xml2process)
                    root = tree.getroot()
                    for child in root.iter('property'):
                        property_name=child.attrib.get('name', None)
                        if property_name == 'geocode bounding box':
                            #print 'property_name: ' + property_name + ' ' + str(child.attrib)
                            #print child[0].text
                            child[0].text = '"' + geocode2_textelement + '"'
                    tree.write(xml2process)

                #verify if raw files from previous run exist:
                #print os.path.join(dir2process, str(int(baselinet_data[i,0]))+'.raw')
                if geocode_reprocess == 1 and (os.path.exists(os.path.join(dir2process_merged, 'filt_topophase.unw')) or \
                    os.path.exists(os.path.join(dir2process_merged, 'filt_topophase.unw'))):
                    cmd = ['topsApp.py', '--steps', '--start=filter', xml2process]
                    print 'Replaced geocode bounding box and running ' + str(i+1) + ' of ' + str(len(date_dt)) + ': ' + ' '.join(cmd)
                    os.chdir(dir2process)
                    start_t = time.time()
                    logfile_fname = os.path.join(dir2process, 'log') + '/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                    logfile_error_fname = os.path.join(dir2process, 'log') + '/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
                    with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                        subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                        subprocess_p.wait()
                    end_t = time.time()
                    ifg_proc_ok = 1
                    print 'Duration: ' + str(round((end_t-start_t)/60., 2)) + ' minutes or ' + str(round((end_t-start_t)/60./60., 2)) + ' hours'
#os.path.exists(os.path.join(dir2process, 'filt_topophase_2stage.unw')) == False or
            elif os.path.exists(os.path.join(dir2process_merged, 'filt_topophase.unw')) == False:
                cmd = ['topsApp.py', '--steps', xml2process]
                print 'Generating interferogram: ' + str(i+1) + ' of ' + str(len(date_dt)) + ': ' + ' '.join(cmd)
                os.chdir(dir2process)
                start_t = time.time()
                logfile_fname = os.path.join(dir2process, 'log') + '/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                logfile_error_fname = os.path.join(dir2process, 'log') + '/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                    subprocess_p.wait()
                end_t = time.time()
                #verify if ifg is ok:
                ifg_proc_ok = 1
                print 'Duration: ' + str(round((end_t-start_t)/60., 2)) + ' minutes or ' + str(round((end_t-start_t)/60./60., 2)) + ' hours'

#            elif os.path.exists(os.path.join(dir2process, 'filt_topophase_2stage.unw')) == False and \
#                    os.path.exists(os.path.join(dir2process, 'filt_topophase.unw')) == True:
#                cmd = ['topsApp.py', '--steps', '--start=unwrap2stage', xml2process]
#                print 'Replaced geocode bounding box and running ' + str(i+1) + ' of ' + str(len(date_dt)) + ': ' + ' '.join(cmd)
#                os.chdir(dir2process)
#                start_t = time.time()
#                logfile_fname = 'log/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
#                logfile_error_fname = 'log/topsApp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
#                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
#                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
#                    subprocess_p.wait()
#                end_t = time.time()
#                print 'Duration: ' + str(round((end_t-start_t)/60., 2)) + ' minutes or ' + str(round((end_t-start_t)/60./60., 2)) + ' hours'
#
            elif (os.path.exists(os.path.join(dir2process_merged, 'filt_topophase.unw.geo')) == True and geocode_reprocess == 0):
                print 'filt_topophase.unw exists and no geocode_reprocessing set'
                ifg_proc_ok = 1

            if i == 0:
                print 'Generating additional geocoded files for first file in date list: ', dir2process
                os.chdir(dir2process)

                if os.path.exists(os.path.join(dir2process_merged,'filt_topophase.unw.geo.xml')) == False:
                    print 'topsApp.py failed on : ' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S')
                    ifg_proc_ok = 0
                    continue

                tree = ET.parse(os.path.join(dir2process_merged,'filt_topophase.unw.geo.xml'))
                root = tree.getroot()
                coord = root.findall('component')
                if sensor_name == 'Sentinel1' or sensor_name == 'Sentinel1A' or sensor_name == 'Sentinel1B':
                    width = coord[0].findall('property')[4][0].text
                    length = coord[1].findall('property')[4][0].text
                    stepsize_degree = float(coord[0].findall('property')[0][0].text)
                    lon2 = coord[0].findall('property')[5][0].text
                    lon1 = float(lon2) + (stepsize_degree * float(width))
                    lat1 = coord[1].findall('property')[1][0].text
                    lat2 = coord[1].findall('property')[5][0].text
                elif sensor_name == 'ALOS':
                    width = coord[0].findall('property')[4][0].text
                    length = coord[1].findall('property')[1][0].text
                    lon1 = coord[0].findall('property')[1][0].text
                    lon2 = coord[0].findall('property')[5][0].text
                    lat1 = coord[1].findall('property')[1][0].text
                    lat2 = coord[1].findall('property')[5][0].text
                if os.path.exists(os.path.join(dir2process,'fine_interferogram.xml')):
                    file2grep = os.path.join(dir2process,'fine_interferogram.xml')
                elif os.path.exists(os.path.join(dir2process,'fine_interferogram/IW1.xml')):
                    file2grep = os.path.join(dir2process,'fine_interferogram/IW1.xml')
                elif os.path.exists(os.path.join(dir2process,'fine_interferogram/IW2.xml')):
                    file2grep = os.path.join(dir2process,'fine_interferogram/IW2.xml')
                elif os.path.exists(os.path.join(dir2process,'fine_interferogram/IW3.xml')):
                    file2grep = os.path.join(dir2process,'fine_interferogram/IW3.xml')
                tree = ET.parse(file2grep)
                doc = tree.getroot()
                rangepixelsize = doc[1][2][9][25][0].text
                radarwavelength = doc[1][2][9][24][0].text
#                geofile2grep = os.path.join(dir2process_merged,'filt_topophase.unw.geo.xml')
#                tree = ET.parse(geofile2grep)
#                doc = tree.getroot()
#                length=doc[10][0].text
#                width=doc[14][0].text
                print 'rangepixelsize: (m)', rangepixelsize, ', radarwavelength: (m)', radarwavelength, '\nwidth: ', str(width), ', length: ', str(length)
                #print 'lat1: ', lat1, ', lat2:', lat2, ', lon1: ', lon1, ', lon2: ', lon2, ', stepsize: ', stepsize_degree

                #PEG_HEADING
                os.chdir(dir2process_merged)
                cmd = ['gdal_translate', '-ot',  'Float32', '-of', 'ENVI', 'dem.crop', 'dem.crop.float32']
                logfile_fname = dir2process + '/log/gdalwarp' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                logfile_error_fname = dir2process + '/log/gdalwarp' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                    subprocess_p.wait()

                os.chdir(dir2process)
                if os.path.exists(os.path.join(dir2process,'merged/los.rdr.geo.vrt')):
                    os.remove(os.path.join(dir2process,'merged/los.rdr.geo.vrt'))
                cmd = ['isce2gis.py', 'vrt', '-i', 'merged/los.rdr.geo']
                logfile_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                logfile_error_fname = dir2process + '/log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                    subprocess_p.wait()
                os.chdir(dir2process_merged)
                cmd = ['gdal_edit.py', '-a_nodata', '0.0', 'los.rdr.geo.vrt']
                logfile_fname = dir2process + '/log/gdal_edit_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                logfile_error_fname = dir2process + '/log/gdal_edit_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                    subprocess_p.wait()
                cmd = ['gdalinfo', '-hist',  '-stats', 'los.rdr.geo.vrt']
                logfile_fname = dir2process + '/log/gdalinfo_stats_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                logfile_error_fname = dir2process + '/log/gdalinfo_stats_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                    subprocess_p.wait()

                incidence_flag = 0
                with open(logfile_fname) as searchfile:
                    for line in searchfile:
                        left,sep,right = line.partition('STATISTICS_MEAN=')
                        if sep: # True if 'STATISTICS_MEAN' in line
                            if incidence_flag == 0:
                                incidence_degree = float(right)
                                print 'LOS: Mean incidence angle (degree): ' + str(incidence_degree)
                                incidence_flag = 1
#                            else:
#                                azimuth = 180.0 - float(right)
#                                heading  = azimuth - 90.0
#                                PEG_HEADING = azimuth - 90.0
#                                print 'LOS: Azimuth angle from north (degree): ' + str(float(right)) + ', azimuth = ' + str(azimuth) + ', PEG_HEADING = ' + str(PEG_HEADING)
                os.chdir(dir2process)
                try:
                    PEG_HEADING
                except NameError:
                    incidence_flag = 0
                    searchfile_stats = max(glob.iglob('log/gdalinfo_stats_*.txt'), key=os.path.getctime)
                    with open(searchfile_stats) as searchfile:
                        for line in searchfile:
                            left,sep,right = line.partition('STATISTICS_MEAN=')
                            if sep: # True if 'STATISTICS_MEAN' in line
                                if incidence_flag == 0:
                                    incidence_degree = float(right)
                                    print 'LOS: Mean incidence angle (degree): ' + str(incidence_degree)
                                    incidence_flag = 1
                                #else:
                                    #calculations are not correct:
                                    #azimuth = 180.0 - float(right)
                                    #heading  = azimuth - 90.0
                                    #PEG_HEADING = azimuth - 90.0
                                    #print 'LOS: Azimuth angle from north (degree): ' + str(float(right)) + ', azimuth = ' + str(azimuth) + ', PEG_HEADING = ' + str(PEG_HEADING)

                # get PEG_HEADING from isce.log
                searchfile_iscelog = os.path.join(dir2process, 'isce.log')
                with open(searchfile_iscelog) as searchfile:
                    for line in searchfile:
                        left,sep,right = line.partition('isce.zerodop.topozero - WARNING - Default Peg heading set to: ')
                        if sep: # True if 'STATISTICS_MEAN' in line
                            #print 'PEG_HEADING: ' + str(float(right))
                            PEG_HEADING = float(right)
                print 'PEG_HEADING: ' + str(PEG_HEADING)

                #now convert files to format that can be read by GIANT
                print 'Writing dem_crop_rsc: ', os.path.join(dir2process_merged,'dem.crop.float32.rsc')
                dem_crop_rsc = open(os.path.join(dir2process_merged,'dem.crop.float32.rsc'), 'wb')
                dem_crop_rsc.write('WIDTH\t\t\t\t%d\n' % int(width))
                dem_crop_rsc.write('FILE_LENGTH\t\t\t%d\n' % int(length))
                dem_crop_rsc.write('RANGE_PIXEL_SIZE\t\t%s\n' % rangepixelsize)
                dem_crop_rsc.write('AZIMUTH_PIXEL_SIZE\t\t%s\n' % rangepixelsize)
                dem_crop_rsc.write('LAT_REF1\t\t\t%s\n' % lat2)
                dem_crop_rsc.write('LON_REF1\t\t\t%s\n' % lon2)
                dem_crop_rsc.write('LAT_REF2\t\t\t%s\n' % lat2)
                dem_crop_rsc.write('LON_REF2\t\t\t%s\n' % lon1)
                dem_crop_rsc.write('LAT_REF3\t\t\t%s\n' % lat1)
                dem_crop_rsc.write('LON_REF3\t\t\t%s\n' % lon2)
                dem_crop_rsc.write('LAT_REF4\t\t\t%s\n' % lat1)
                dem_crop_rsc.write('LON_REF4\t\t\t%s\n' % lon1)
                dem_crop_rsc.close()

                try:
                    label_txt
                except NameError:
                    insarproc_xml_fname = os.path.join(indir_path, 'S1_InSARproc.py')
                else:
                    insarproc_xml_fname = os.path.join(indir_path, 'S1_InSARproc_'+label_txt+'.py')
                if os.path.exists(insarproc_xml_fname) == False:
                    f = open(insarproc_xml_fname, 'w+')
                    f.write('<insarProc>\n')
                    f.write('\t<insarProc>\n')
                    f.write('\t\t<ISCE_VERSION>Release: 2.0.0_201512, svn-1931, 20151221. Current svn-Unversioned directory</ISCE_VERSION>\n')
                    f.write('\t</insarProc>\n')
                    f.write('\t<master>\n')
                    f.write('\t\t<sensor>\n')
                    f.write('\t\t\t<family>Sentinel-1</family>\n')
                    f.write('\t\t\t<name>master</name>\n')
                    f.write('\t\t</sensor>\n')
                    f.write('\t\t<frame>\n')
                    f.write('\t\t\t<SENSING_START>2015-03-15 21:25:39.991827</SENSING_START>\n')
                    f.write('\t\t</frame>\n')
                    f.write('\t</master>\n')
                    f.write('\t<runGeocode>\n')
                    f.write('\t\t<outputs>\n')
                    f.write('\t\t\t<GEO_WIDTH>%d</GEO_WIDTH>\n' %int(width))
                    f.write('\t\t\t<GEO_LENGTH>%d</GEO_LENGTH>\n' %int(length))
                    f.write('\t\t</outputs>\n')
                    f.write('\t</runGeocode>\n')
                    f.write('\t<runTopo>\n')
                    f.write('\t\t<inputs>\n')
                    f.write('\t\t\t<PEG_HEADING>%s</PEG_HEADING>\n'%str(PEG_HEADING))
                    f.write('\t\t\t<RADAR_WAVELENGTH>%s</RADAR_WAVELENGTH>\n' %radarwavelength)
                    f.write('\t\t</inputs>\n')
                    f.write('\t</runTopo>\n')
                    f.write('</insarProc>\n')
                    f.close()

#                #generate prepare_xmls_pocitos_Sentinel1A.py
                try:
                    label_txt
                except NameError:
                    prepare_xmls_fname = os.path.join(indir_path, 'prepare_xmls.py')
                else:
                    prepare_xmls_fname = os.path.join(indir_path, 'prepare_xmls_'+label_txt+'.py')
                if os.path.exists(prepare_xmls_fname) == False:
                    f = open(prepare_xmls_fname, 'w+')
                    f.write('#!/usr/bin/env python\n\nimport tsinsar as ts\n')
                    f.write('import argparse\n')
                    f.write('import numpy as np\n\n')
                    f.write("if __name__ == '__main__': \n")
                    f.write("\tg = ts.TSXML('data')\n")
                    f.write("\tg.prepare_data_xml('%s', proc='ISCE', inc = %s, cohth=0.1, chgendian='False', rxlim = [500,500], rylim=[510,510], unwfmt='RMG', corfmt='FLT', demfmt='FLT', hgtfile='%s/merged/dem.crop.float32', latfile='%s/merged/lat.rdr.geo', lonfile='%s/merged/lon.rdr.geo')\n"%(insarproc_xml_fname, str(incidence_degree), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1])))))
                    f.write("\tg.writexml('data.xml')\n\n")
                    f.write("\tg = ts.TSXML('params')\n")
                    f.write("\tg.prepare_sbas_xml(nvalid=%d,netramp=True,atmos='',demerr=False,uwcheck=False,regu=True,masterdate='%s',filt=0.1)\n" % (int(round(np.divide(len(date_dt),1), 0)), str(int(baselinet_data[i,0]))))
                    f.write("\tg.writexml('sbas.xml')\n\n")
                    f.write("\tg = ts.TSXML('params')\n")
                    f.write("\tg.prepare_mints_xml(netramp=True,atmos='',demerr=False,uwcheck=False,regu=True,minscale=2,wvlt='meyer')\n")
                    f.write("\tg.writexml('mints.xml')\n\n")
                    f.write("\tg = ts.TSXML('data')\n")
                    f.write("\tg.prepare_data_xml('%s', proc='ISCE', inc = %s, cohth=0.1, chgendian='False', rxlim = [500,500], rylim=[510,510], unwfmt='RMG', corfmt='FLT', demfmt='FLT', hgtfile='%s/merged/dem.crop.float32', latfile='%s/merged/lat.rdr.geo', lonfile='%s/merged/lon.rdr.geo')\n"%(insarproc_xml_fname, str(incidence_degree), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1])))))
                    f.write("\tg.writexml('data_ECMWF.xml')\n\n")
                    f.write("\tg = ts.TSXML('params')\n")
                    f.write("\tg.prepare_sbas_xml(nvalid=%d,netramp=True,atmos='ECMWF',demerr=False,uwcheck=False,regu=True,masterdate='%s',filt=0.1)\n" % (int(round(np.divide(len(date_dt),1), 0)), str(int(baselinet_data[i,0]))))
                    f.write("\tg.writexml('sbas_ECMWF.xml')\n\n")
                    f.write("\tg = ts.TSXML('params')\n")
                    f.write("\tg.prepare_mints_xml(netramp=True,atmos='ECMWF',demerr=False,uwcheck=False,regu=True,minscale=2,wvlt='meyer')\n")
                    f.write("\tg.writexml('mints_ECMWF.xml')\n\n")
                    f.write("\tg = ts.TSXML('data')\n")
                    f.write("\tg.prepare_data_xml('%s', proc='ISCE', inc = %s, cohth=0.1, chgendian='False', rxlim = [500,500], rylim=[510,510], unwfmt='RMG', corfmt='FLT', demfmt='FLT', hgtfile='%s/merged/dem.crop.float32', latfile='%s/merged/lat.rdr.geo', lonfile='%s/merged/lon.rdr.geo')\n"%(insarproc_xml_fname, str(incidence_degree), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1]))), str(str(int(baselinet_data[i,0])) + '_' + str(int(baselinet_data[i,1])))))
                    f.write("\tg.writexml('data_TROPO.xml')\n\n")
                    f.write("\tg = ts.TSXML('params')\n")
                    f.write("\tg.prepare_sbas_xml(nvalid=%d,netramp=True,atmos='TROPO',demerr=False,uwcheck=False,regu=True,masterdate='%s',filt=0.1)\n" % (int(round(np.divide(len(date_dt),1), 0)), str(int(baselinet_data[i,0]))))
                    f.write("\tg.writexml('sbas_TROPO.xml')\n\n")
                    f.write("\tg = ts.TSXML('params')\n")
                    f.write("\tg.prepare_mints_xml(netramp=True,atmos='TROPO',demerr=False,uwcheck=False,regu=True,minscale=2,wvlt='meyer')\n")
                    f.write("\tg.writexml('mints_TROPO.xml')\n")
                    f.close()
                os.chdir(indir_path)
                cmd = ['/usr/bin/python', prepare_xmls_fname]
                logfile_fname = indir_path + '/log_output/prepare_xmls_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
                logfile_error_fname = indir_path + '/log_output/prepare_xmls_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
                    subprocess_p.wait()

                if os.path.exists(os.path.join(indir_path, 'userfn.py')) == False:
                    f = open(os.path.join(indir_path, 'userfn.py'), 'w+')
                    f.write('def makefnames(dates1,dates2,sensor):\n')
                    f.write("\tdirname = '%s'\n" % indir_path)
                    f.write("\tif sensor in ('TerraSARX'):\n")
                    f.write("\t\tiname = '%s/%s_%s/filt_topophase_2stage.unw.geo'%(dirname,dates1,dates2)\n")
                    f.write("\t\tcname = '%s/%s_%s/topophase.cor.geo'%(dirname,dates1,dates2)\n")
                    f.write("\telif sensor in ('ALOS'):\n")
                    f.write("\t\tiname = '%s/%s_%s/filt_topophase_2stage.unw.geo'%(dirname,dates1,dates2)\n")
                    f.write("\t\tcname = '%s/%s_%s/topophase.cor.geo'%(dirname,dates1,dates2)\n")
                    f.write("\telif sensor in ('ENVISAT'):\n")
                    f.write("\t\tiname = '%s/%s_%s/filt_topophase_2stage.unw.geo'%(dirname,dates1,dates2)\n")
                    f.write("\t\tcname = '%s/%s_%s/topophase.cor.geo'%(dirname,dates1,dates2)\n")
                    f.write("\telif sensor in ('Sentinel1'):\n")
                    #f.write("\t\tiname = '%s/%s_%s/merged/filt_topophase.unw.geo'%(dirname,dates1,dates2,'" + "')\n")
                    f.write("\t\tiname = '%s/%s_%s/merged/filt_topophase_2stage.unw.geo'%(dirname,dates1,dates2,'" + "')\n")
                    f.write("\t\tcname = '%s/%s_%s/merged/phsig.cor.geo'%(dirname,dates1,dates2,'" + "')\n")
                    f.write("\telse:\n")
                    f.write("\t\tprint 'Unknown sensor.'\n")
                    f.write("\t\tsys.exit(1)\n")
                    f.write('\treturn iname,cname\n\n')
                    f.write('def NSBASdict():\n')
                    f.write("\trep = [['POLY',[1],[tims[Ref]]],['LOG'],[-2.0],[3.0]]\n")
                    f.write('\treturn rep\n\n')
                    f.write('def timedict():\n')
                    f.write("\trep = [['ISPLINES',[3],[48]]]\n")
                    f.write('\treturn rep\n\n')
                    f.close()



                os.chdir(dir2process)

            os.chdir(dir2process)
            #remove .raw files to save space
            #remove .raw files only of processing went well!
            #print 'do_not_delete: ' + str(do_not_delete) + ', ifg_proc_ok: ' + str(ifg_proc_ok)
            if do_not_delete == 0 and ifg_proc_ok == 1 and i > 0:
                print 'Cleaning up and removing all processing directories and files'

                if os.path.exists(os.path.join(dir2process,'coarse_coreg')):
                    files2remove = os.path.join(dir2process, 'coarse_coreg')
                    shutil.rmtree(files2remove)
                    files2remove = os.path.join(dir2process, 'coarse*.xml')
                    files2remove = glob.glob(files2remove)
                    for j in files2remove:
                        os.remove(j)

                if os.path.exists(os.path.join(dir2process,'coarse_interferogram')):
                    files2remove = os.path.join(dir2process, 'coarse_interferogram')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'coarse_offsets')):
                    files2remove = os.path.join(dir2process, 'coarse_offsets')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'ESD')):
                    files2remove = os.path.join(dir2process, 'ESD')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'fine_offsets')):
                    files2remove = os.path.join(dir2process, 'fine_offsets')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'fine_coreg')):
                    files2remove = os.path.join(dir2process, 'fine_coreg')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'fine_interferogram')):
                    files2remove = os.path.join(dir2process, 'fine_interferogram')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'geom_master')):
                    files2remove = os.path.join(dir2process, 'geom_master')
                    shutil.rmtree(files2remove)
                    files2remove = os.path.join(dir2process, 'fine*.xml')
                    files2remove = glob.glob(files2remove)
                    for j in files2remove:
                        os.remove(j)

            if do_not_delete == 2 and ifg_proc_ok == 1 and i > 0:
                print 'Cleaning up and removing some processing directories and files'

                if os.path.exists(os.path.join(dir2process,'coarse_coreg')):
                    files2remove = os.path.join(dir2process, 'coarse_coreg')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'coarse_interferogram')):
                    files2remove = os.path.join(dir2process, 'coarse_interferogram')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'coarse_offsets')):
                    files2remove = os.path.join(dir2process, 'coarse_offsets')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'ESD')):
                    files2remove = os.path.join(dir2process, 'ESD')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'fine_offsets')):
                    files2remove = os.path.join(dir2process, 'fine_offsets')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'fine_coreg')):
                    files2remove = os.path.join(dir2process, 'fine_coreg')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'fine_interferogram')):
                    files2remove = os.path.join(dir2process, 'fine_interferogram')
                    shutil.rmtree(files2remove)
                if os.path.exists(os.path.join(dir2process,'geom_master')):
                    files2remove = os.path.join(dir2process, 'geom_master')
                    shutil.rmtree(files2remove)
                    #files2remove = os.path.join(dir2process, 'fine*.xml')
                    #files2remove = glob.glob(files2remove)
                    #for j in files2remove:
                    #    os.remove(j)

            #ADD HERE: remove files from .SAFE directory: master and slave
            os.chdir(dir2process)
            #date2process = '_'.join(dir2process.split('/')[-2:-1])
            date2process = dir2process_noswath
            #print 'date2process: ' + date2process
            if generate_png == 1:
                if os.path.exists('log') == False:
                    os.mkdir('log')
                if len(glob.glob(os.path.join(dir2process,os.path.join(dir2process, 'merged_views_' + date2process + '.png')))) > 0:
                    print 'PNG exists for: ' + os.path.join(dir2process, 'merged_views_' + date2process + '.png')
                else:
                    generate_single_png(topophase_min, topophase_max, indir, dir2process_merged, date2process, False)

            if generate_utm_geotif == 1:
                os.chdir(dir2process)
                if os.path.exists('log') == False:
                    os.mkdir('log')
                if len(glob.glob(os.path.join(indir,os.path.join(dir2process, 'merged/*' + date2process + '.tif')))) > 0:
                    print 'Geotifs exists for: ' + date2process
                else:
                    generate_single_geotif_utm(dir2process, dir2process_merged, date2process, label_txt, baselinet_data, float(radarwavelength))


    os.chdir(origWD)
    mean_fname = 'conncomp_mean.list'
    mean_fname = os.path.join(indir_path, mean_fname)
    if len(conncomp_mean) > 1:
        with open(mean_fname, 'wb') as myfile:
            wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for conncomp_mean_item in conncomp_mean:
                wr.writerow([conncomp_mean_item])

    mean_fname = 'los_mean.list'
    mean_fname = os.path.join(indir_path, mean_fname)
    if len(los_mean) > 1:
        with open(mean_fname, 'wb') as myfile:
            wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for los_mean_item in los_mean:
                wr.writerow([los_mean_item])

    min_fname = 'los_min.list'
    min_fname = os.path.join(indir_path, mean_fname)
    if len(los_min) > 1:
        with open(min_fname, 'wb') as myfile:
            wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for los_min_item in los_min:
                wr.writerow([los_min_item])

    max_fname = 'los_max.list'
    max_fname = os.path.join(indir_path, max_fname)
    if len(los_max) > 1:
        with open(max_fname, 'wb') as myfile:
            wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for los_max_item in los_max:
                wr.writerow([los_max_item])

    mean_fname = 'los2_mean.list'
    mean_fname = os.path.join(indir_path, mean_fname)
    if len(los2_mean) > 1:
        with open(mean_fname, 'wb') as myfile:
            wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for los_mean_item in los2_mean:
                wr.writerow([los_mean_item])

    min_fname = 'los2_min.list'
    min_fname = os.path.join(indir_path, mean_fname)
    if len(los2_min) > 1:
        with open(min_fname, 'wb') as myfile:
            wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for los_min_item in los2_min:
                wr.writerow([los_min_item])

    max_fname = 'los2_max.list'
    max_fname = os.path.join(indir_path, max_fname)
    if len(los2_max) > 1:
        with open(max_fname, 'wb') as myfile:
            wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for los_max_item in los2_max:
                wr.writerow([los_max_item])

    idx_fname = 'idx_with_low_conncomp.list'
    idx_fname = os.path.join(indir_path, idx_fname)
    if len(conncomp_2use_idx) > 1:
        with open(idx_fname, 'wb') as myfile:
            wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
            for idx_item in conncomp_2use_idx:
                wr.writerow([idx_item])
    if os.path.exists(idx_fname):
        f = open(idx_fname, 'rt')
        conncomp_2use_idx_csv = csv.reader(f)
        conncomp_2use_idx = list(conncomp_2use_idx_csv)
        conncomp_2use_idx = [int(i[0]) for i in conncomp_2use_idx]


    ifg_fname = 'ifg.list'
    ifg_fname = os.path.join(indir_path, ifg_fname)
    with open(ifg_fname, 'wb') as myfile:
        wr = csv.writer(myfile, delimiter='\t', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        #wr.writerow(['Masterdate', 'Slavedate', 'Bperp_in_m', 'Sensor'])
        for i in range(len(conncomp_2use_idx)):
            item = baseline_results_lt_threshold[conncomp_2use_idx[i]]
            wr.writerow([item[0], item[1], item[3], sensor_name])

    #write only baselines with perpendicular baseline < THRESHOLD
    baseline_fname = label_txt + '_conncomp_los_baseline_results_lt_' + str(PERP_BASELINE_THRESHOLD) + '.csv'
    baseline_results_lt_threshold_csv = os.path.join(indir_path, baseline_fname)
    with open(baseline_results_lt_threshold_csv, 'wb') as myfile:
        wr = csv.writer(myfile, delimiter=',', quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        wr.writerow(['Date1', 'Date2', 'DeltaDate_yr', 'Perp_baseline', 'Nr_of_scenes', 'Scene1', 'Scene2'])
        for item in baseline_results_lt_threshold_conncomp_los:
            wr.writerow([item[0], item[1], item[2], item[3], item[4], item[5], item[6]])

    #generate merged PDF files with 5 images per page
    os.chdir(indir)
    append_list = glob.glob(os.path.join(indir, '*/merged_views_*' + '.png'))
    append_list.sort()
    png_file_basename = append_list
    #slice into groups of five
    png_file_list = range(0,len(append_list),5)
    counter = 1
    png_filenames = []
    for i in png_file_list:
        print 'Combine png file ' + str(counter) + ' of ' + str(len(png_file_list)) + ' files'
        if counter < len(png_file_list):
            cmd6a = ['convert', png_file_basename[i], png_file_basename[i+1], png_file_basename[i+2], png_file_basename[i+3], png_file_basename[i+4], '-append', 'merged_views_' +  str(counter) + '.png']
            #cmd6b = ['convert', os.path.basename(dir2process) + '.png', os.path.basename(dir2process) + '.pdf']
            logfile_fname = 'log_output/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = 'log_output/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            if not os.path.exists('merged_views_' +  str(counter) + '.png'):
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd6a, stdout=out, stderr=err)
                    subprocess_p.wait()
        elif counter == len(png_file_list):
            #last element
            nr_of_last_elements = len(append_list) - i
            if nr_of_last_elements == 4:
                cmd6a = ['convert', png_file_basename[i], png_file_basename[i+1], png_file_basename[i+2], png_file_basename[i+3], '-append', 'merged_views_' +  str(counter) + '.png']
            elif nr_of_last_elements == 3:
                cmd6a = ['convert', png_file_basename[i], png_file_basename[i+1], png_file_basename[i+2], '-append', 'merged_views_' +  str(counter) + '.png']
            elif nr_of_last_elements == 2:
                cmd6a = ['convert', png_file_basename[i], png_file_basename[i+1], '-append', 'merged_views_' +  str(counter) + '.png']
            elif nr_of_last_elements == 1:
                cmd6a = ['convert', png_file_basename[i], '-append', 'merged_views_' +  str(counter) + '.png']
            logfile_fname = 'log_output/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
            logfile_error_fname = 'log_output/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
            if not os.path.exists('merged_views_' +  str(counter) + '.png'):
                with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
                    subprocess_p = subprocess.Popen(cmd6a, stdout=out, stderr=err)
                    subprocess_p.wait()
        png_filenames.append('merged_views_' +  str(counter) + '.png')
        counter = counter + 1

    #convert merged_views_1.png merged_views_2.png -resize 1240x1750 -background black -compose Copy -gravity center -extent 1240x1750 -units PixelsPerInch -density 150 merged_views.pdf
    print 'Merge all PNG into one high-res PDF... '
    cmd6a = ['convert', str(' '.join(png_filenames)), '-resize', '1240x1750', '-background', 'black', '-compose', 'Copy', '-gravity', 'center', '-extent', '1240x1750', '-units', 'PixelsPerInch', '-density', '150','-quality', '50', str(label_txt) + '_all_views_1_' +  str(len(png_filenames)) + '.pdf']
    print " ".join(cmd6a)
    #cmd6b = ['convert', os.path.basename(dir2process) + '.png', os.path.basename(dir2process) + '.pdf']
    logfile_fname = 'log_output/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    logfile_error_fname = 'log_output/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
    if not os.path.exists('merged_all_views_1_' +  str(len(png_filenames)) + '.pdf'):
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd6a, stdout=out, stderr=err)
            subprocess_p.wait()
    print 'done'

    print 'Merge all PNG into one low-res PDF... '
    cmd6a = ['convert', str(' '.join(png_filenames)), '-resize', '1240x1750', '-background', 'black', '-compose', 'Copy', '-gravity', 'center', '-extent', '1240x1750', '-units', 'PixelsPerInch', '-density', '72','-quality', '25', str(label_txt) + '_all_views_1_' +  str(len(png_filenames)) + '_lowres.pdf']
    print " ".join(cmd6a)
    #cmd6b = ['convert', os.path.basename(dir2process) + '.png', os.path.basename(dir2process) + '.pdf']
    logfile_fname = 'log_output/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    logfile_error_fname = 'log_output/png_append_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
    if not os.path.exists('merged_all_views_1_' +  str(len(png_filenames)) + '.pdf'):
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd6a, stdout=out, stderr=err)
            subprocess_p.wait()
    print 'done'

#convert DEM to GeoTIFF and Hillshade
dem_path = os.path.abspath(dem_file).split('/')[0:-1]
dem_path = '/'.join(dem_path)
dem_tif = os.path.basename(dem_file).split('.')[0:-1]

if os.path.exists(dem_file):
    os.chdir(dem_path)
    if os.path.exists('log') == False:
        os.mkdir('log')
    print 'Converting SRTM DEM to geotif and hillshade: ' + dem_file
    cmd = ['isce2gis.py', 'vrt', '-i', '.'.join(dem_tif)]
    logfile_fname = 'log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    logfile_error_fname = 'log/isce2gis_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
    with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
        subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
        subprocess_p.wait()

    #print 'DEM: ' + os.path.join(dem_path, '.'.join(dem_tif)+'.xml')
    tree = ET.parse(os.path.join(dem_path, '.'.join(dem_tif)+'.vrt'))
    geotransform = tree.find('GeoTransform').text
    Px = float(geotransform.split(',')[0])
    Py = float(geotransform.split(',')[3])
    Zone = math.floor((Px + 180)/6) + 1
    if Px >= 56.0 and Px <= 64.0 and Zone > 3.0 and Zone < 12.0:
        Zone = 32
    Zone = str(int(Zone))
    if Py > 0:
        prj = '+proj=utm +zone=' + Zone + ' +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
        outtiff = '.'.join(dem_tif) + '_UTM' + Zone + 'N.tif'
    if Py < 0:
        prj = '+proj=utm +zone=' + Zone + ' +south +ellps=WGS84 +datum=WGS84 +units=m +no_defs'
        outtiff = '.'.join(dem_tif) + '_UTM' + Zone + 'S.tif'
    outtiff = os.path.join(dem_path, outtiff)
    if os.path.exists(os.path.join(dir2process,outtiff)) == False:
        cmd = ['gdalwarp', '-multi', '-tap', '-tr', str(args.dem_res), str(args.dem_res), '-t_srs', prj, '-r', 'bilinear', '-co', 'COMPRESS=LZW', '-co', 'predictor=2', os.path.join(dem_path, '.'.join(dem_tif)+'.vrt'), outtiff]
        logfile_fname = 'log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/gdalwarp_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-hist', '-stats', outtiff]
        logfile_fname = 'log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        outiff_HS = outtiff[0:-4] + '_HS.tif'
        cmd = ['gdaldem', 'hillshade', outtiff, outiff_HS]
        logfile_fname = 'log/gdaldem_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/gdaldem_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
        cmd = ['gdalinfo', '-hist', '-stats', outtiff]
        logfile_fname = 'log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '.txt'
        logfile_error_fname = 'log/gdalinfo_' + datetime.datetime.now().strftime('%Y%b%d_%H%M%S') + '_err.txt'
        with open(logfile_fname, 'wb') as out, open(logfile_error_fname, 'wb') as err:
            subprocess_p = subprocess.Popen(cmd, stdout=out, stderr=err)
            subprocess_p.wait()
    os.chdir(origWD)
