# Processing directory with Radar data

## Sentinel-1
[prepare_Sentinel1.py](prepare_Sentinel1.py) is a simple script that call topsApp.py (ISCE), gdal and various other commands to process a directory containing SAR data. An output PDF/png will be created showing all interferograms and a baseline plot will be generated. All parameter and config files for GIAnT processing will be prepared. The snytax contains several options:
<> are required input, -- indicates optional input
```
prepare_Sentinel1.py <indir> <baseline> --dem --dem_res --roi --box --label --proc_steps --geocode_reprocess --do_not_delete --generate_utm_geotif --orbit_dir --aux_dir --swath --generate_png
```

with the following explanation:
- _indir_		directory to be processed (e.g., /raid/InSAR/Sentinel1A/NWArg)
- _baseline_		perpendicular baseline threshold in m
- --dem			DEM to be used for processing (e.g., --dem /raid/InSAR/TerraSAR-X/Pocitos/SRTM1/demLat_S23_S26_Lon_W069_W066_f2.dem.wgs84.xml)
- --roi			region of interest bounding box with S, N, W, E coordinates (include " ", e.g., - --roi "[-24,-24.75,-67.25,-66.75]")
- --box			bounding box with S, N, W, E coordinates (include " ", e.g., --box "[-24,-24.75,-67.25,-66.75]")
- --label			text string indicating label of current area (e.g., --label "salta_lower_qdt")
- --proc_steps		indicating level of processing (e.g., --proc_steps 0 (default) processes all band combinations that are below baseline threshold, --proc_steps 1 is only baseline generation, --proc_steps 2 will generate baselines and only one (first) ifg with full extent, --proc_steps 3 will generate ifgs using the first (oldest) as master with every other scene and then only adjacent pairs, --proc_steps -1 only generates xml control files and does no processing)
- --dem_res			DEM resolution: default is 30 (m) for SRTM-X (use 10 m here for the TanDEM-X). This is only used when converting TIF files to UTM coordinates.
- --geocode_reprocess	Reprocessing unwrapping with a new geocode bounding box. If geocode bounding box has changed and new geocoding is necessary, set this to 1 (e.g., --geocode_reprocess 1)
- --do_not_delete		Delete .raw*, rangeOffset.*, resampImage.*, simamp.* after succesfull interferogram formation. Default = 0 to save space. Set this to 1 to keep all files (e.g., --do_not_delete 1)
- --generate_utm_geotif	Generate geotifs for each interferogram pair. Generates geotif and automatically projects to appropriate UTM Zone X WGS84 coordinate system for all geocoded files. Default = 0 (no tif files are generated). Set this to 1 to generate geotifs (e.g., --generate_utm_geotif 1)
- --orbit_dir		Orbit directory for Sentinel-1 orbits (e.g., --orbit_dir /raid/InSAR/orbits/S1/precise)
- --aux_dir		Instrument and calibration auxiliary directory for Sentinel-1 (e.g., - --aux_dir /raid/InSAR/orbits/S1/aux_ins)
- --swath			Swath of Sentinel1 data (1 to 3, e.g., --swath "[1,2,3]" (default) or --swath "[2,3]" for only swaths 2 and 3)
- --generate_png		Generate PNGs with mdx for each interferogram pair. Generates merged views with unwrapped topophase, phase, correlation, amplitude. Default = 0 (no PNG files are generated). Set this to 1 to generate png (e.g., --generate_png 1). You will need to install imagemick or similar packages to use this option

## Example 1: Typical Sentinel-1 processing example
Copy S1*_IW_SLC_*.zip files for one location (either ascending or descending, but not mixed) to a directory and generate a first interferogram to get extent of image and first impression. Also download the SRTM1 DEM using dem.py:
```
start_isce
dem.py -a stitch -b 33 35 -121 -119 -c -s 1 -k -m xml -r
```
You may consider upsampling the DEM (if necessary) or using a custom DEM:
```
upsampleDem.py -i demLat_N33_N35_Lon_W121_W119.dem.wgs84 -o demLat_N33_N35_Lon_W121_W119_f2.dem.wgs84 -f 2
```

Call prepare_Sentinel1.py and generate a first interferogram: 
```
python2 isce_processing/prepare_Sentinel1.py /raid/InSAR/California/SCI/test 500 \
--label "S1_SCI_SRTM1_30m" \
--dem "/raid/InSAR/California/SCI/SRTM1/demLat_N33_N35_Lon_W121_W119.dem.wgs84" \
--dem_res 30 \
--proc_steps 2 \
--generate_png 1
```

Use QGIS or mdx.py to view the output in the merged directory. Identify the region of interest.


## Example 2: Processing a subset of an IW Sentinel-1 swath
After identifying area of interest, generate a list of interferograms with the first (oldest) images as master and all consecutive images as slave, followed by interferograms for the next pairs (Date2-Date3, Date3-Date4, Date4-Date5, etc). This is --proces_steps 3. Useful, for example, for damage proxy mapping or coherence analysis. This example will generate compiled PNGs of unwrapped phase, connected components, interferometric phase for each date pair and also a merged PDF containing all generated interferograms.

Importantly, this example creates GeoTIFF files in GEOGRAPHIC-WGS84 coordinates and in their respective UTM projection in the merged directory.

```
python2 isce_processing/prepare_Sentinel1.py /raid/InSAR/California/SCI/test 500 \
--label "S1_SCI_SRTM1_30m" \
--dem "/raid/InSAR/California/SCI/SRTM1/demLat_N33_N35_Lon_W121_W119.dem.wgs84" \
--dem_res 30 \
--proc_steps 3 \
--generate_png 1 \
--roi "[34,34.5,-120,-119.2]" \
--box "[33.917,34.112,-119.943,-119.479]" \
--swath "[2]" \
--do_not_delete 1 \
--generate_utm_geotif 1 \
--generate_png 1
```


## Example 3: Processing a subset of an IW Sentinel-1 swath
In this example, the area of interest and area that will be geocoded is between two swaths. These will be automatically merged, clipped and geocoded

```
python2 /home/bodo/Dropbox/soft/ISCE/isce_processing/prepare_Sentinel1.py /raid/InSAR/NWArg/S1/Pocitos 500 \
--dem /raid/InSAR/NWArg/SRTM1/demLat_S28_S22_Lon_W070_W062.dem.wgs84 \
--dem_res 30 \
--label "S1_Pocitos_SRTM1_30m" \
--proc_steps 1 \
--roi "[-25.25, -23, -68, -66]" \
--box "[-25, -23.55, -67.84, -66.30]" \
--swath "[2,3]" \
--do_not_delete 1 \
--generate_utm_geotif 1 \
--generate_png 1
```


## Example 4: Generating xml control files with no processing
Generate only xml control files through --proc_steps -1. This will allow manual exploration of data and files.

```
python2 isce_processing/prepare_Sentinel1.py /raid/InSAR/California/SCI/test 500 \
--label "S1_SCI_SRTM1_30m" \
--dem "/raid/InSAR/California/SCI/SRTM1/demLat_N33_N35_Lon_W121_W119.dem.wgs84" \
--proc_steps -1 \
--roi "[34,34.5,-120,-119.2]" \
--box "[33.917,34.112,-119.943,-119.479]" \
--swath "[2]" \
```
