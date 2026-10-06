"""Offline, windowed GOES-19 ABI C13 brightness-temperature proof.

The geostationary ellipsoid navigation has no cloud parallax correction. Its
conservative DQF=0 / zenith<=75 policy is part of the normalization identity.
"""
from datetime import datetime
from pathlib import Path
import time

from netCDF4 import Dataset
import numpy as np
from pyproj import CRS, Transformer

from .grid import write_grid
from .model import CaptureManifest, ProductArtifact, capture_manifest_path, object_path

EXPANDED_LIMIT = 256 * 1024**2
WINDOW_ROWS = 128
NORMALIZATION_VERSION = "diagnostic-goes19-c13-dqf0-zenith75-bilinear-instant-v2"


def _timestamp(value):
    instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if instant.utcoffset() is None:
        raise ValueError('scan interval requires explicit timezone')
    return round(instant.timestamp() * 1000)


def _expanded_bytes(dataset):
    # Conservative potential unpacked storage: scaled fields as Float64,
    # unscaled fields retain their native dtype. No science arrays read yet.
    total = sum(int(v.size) * (max(v.dtype.itemsize, 8) if 'scale_factor' in v.ncattrs() or 'add_offset' in v.ncattrs() else v.dtype.itemsize) for v in dataset.variables.values())
    if total > EXPANDED_LIMIT:
        raise ValueError('expanded NetCDF object exceeds 256 MiB cap')
    return total


def _zenith(longitude, latitude, a, b, height, lon0):
    # Ellipsoidal geodetic normal dotted with the surface-to-satellite vector.
    finite=np.isfinite(longitude)&np.isfinite(latitude)
    lat=np.deg2rad(np.where(finite,latitude,0)); lon=np.deg2rad(np.where(finite,longitude-lon0,0))
    e2=1-(b/a)**2
    radius=a/np.sqrt(1-e2*np.sin(lat)**2)
    px=radius*np.cos(lat)*np.cos(lon)
    py=radius*np.cos(lat)*np.sin(lon)
    pz=radius*(1-e2)*np.sin(lat)
    dx=height+a-px; dy=-py; dz=-pz
    cosine=(dx*np.cos(lat)*np.cos(lon)+dy*np.cos(lat)*np.sin(lon)+dz*np.sin(lat))/np.sqrt(dx*dx+dy*dy+dz*dz)
    return np.where(finite,np.rad2deg(np.arccos(np.clip(cosine,-1,1))),np.nan)


def _axis(variable):
    if variable.units!='rad' or variable.ndim!=1 or not 2<=variable.size<=6000:
        raise ValueError('unsupported satellite navigation coordinates')
    axis=np.asarray(variable[:],dtype='f8')
    spacing=np.diff(axis)
    if not np.isfinite(axis).all() or not ((spacing>0).all() or (spacing<0).all()):
        raise ValueError('unsupported satellite navigation coordinates')
    return axis


def _indices(axis, query):
    # Ascending search with original source indices; supports either scan order.
    ordered=axis if axis[-1]>axis[0] else axis[::-1]
    inside=np.isfinite(query)&(query>=ordered[0])&(query<=ordered[-1])
    safe=np.where(inside,query,ordered[0])
    low=np.clip(np.searchsorted(ordered,safe,side='right')-1,0,len(axis)-2)
    fraction=(safe-ordered[low])/(ordered[low+1]-ordered[low])
    if axis[-1]>axis[0]: return low,low+1,fraction,inside
    return len(axis)-1-low,len(axis)-2-low,fraction,inside


def _regrid(dataset, projection):
    result=np.zeros((361,720),dtype='f8'); mask=np.ones((361,720),dtype='u1')
    if projection.grid_mapping_name!='geostationary' or projection.sweep_angle_axis!='x' or projection.latitude_of_projection_origin!=0:
        return result,mask,{'supported':False,'window_rows':WINDOW_ROWS,'windows_read':0}
    a=float(projection.semi_major_axis); b=float(projection.semi_minor_axis)
    height=float(projection.perspective_point_height); lon0=float(projection.longitude_of_projection_origin)
    if not all(np.isfinite([a,b,height,lon0])) or not 0<b<=a or height<=0:
        raise ValueError('invalid geostationary projection')
    source_crs=CRS.from_proj4(f'+proj=geos +h={height} +lon_0={lon0} +a={a} +b={b} +sweep=x +units=m')
    forward=Transformer.from_crs(source_crs.geodetic_crs,source_crs,always_xy=True)
    reverse=Transformer.from_crs(source_crs,source_crs.geodetic_crs,always_xy=True)
    x=_axis(dataset.variables['x']); y=_axis(dataset.variables['y'])
    cmi=dataset.variables['CMI']; dqf=dataset.variables['DQF']
    if cmi.shape!=(len(y),len(x)) or dqf.shape!=cmi.shape:
        raise ValueError('source field dimensions disagree with navigation')
    cmi.set_auto_maskandscale(False); dqf.set_auto_maskandscale(False)
    cmi.set_var_chunk_cache(size=4*1024**2,nelems=1009,preemption=.5)
    dqf.set_var_chunk_cache(size=1024**2,nelems=1009,preemption=.5)
    lons,lats=np.meshgrid(-180+np.arange(720)*.5,90-np.arange(361)*.5)
    target_x,target_y=forward.transform(lons,lats)
    visible=np.isfinite(target_x)&np.isfinite(target_y)
    zenith=_zenith(lons,lats,a,b,height,lon0)
    mask[visible & (zenith>75)] = 3
    ix0,ix1,wx,inside_x=_indices(x,target_x/height)
    iy0,iy1,wy,inside_y=_indices(y,target_y/height)
    accepted=visible & (zenith<=75) & inside_x & inside_y
    mask[accepted]=0
    # Each source strip is read once per contributor pass; there is never a
    # full-disk decoded array, nor filling from neighboring valid contributors.
    windows=0; peak_window=0
    for ys,yw in ((iy0,1-wy),(iy1,wy)):
        for xs,xw in ((ix0,1-wx),(ix1,wx)):
            weights=(yw*xw).ravel(); rows=ys.ravel(); columns=xs.ravel()
            selected=np.flatnonzero(accepted.ravel() & (weights>0))
            order=selected[np.argsort(rows[selected]//WINDOW_ROWS,kind='stable')]
            groups=rows[order]//WINDOW_ROWS
            boundaries=np.r_[0,np.flatnonzero(np.diff(groups))+1,len(order)]
            for first,last in zip(boundaries[:-1],boundaries[1:]):
                points=order[first:last]
                if not len(points): continue
                row_start=int(groups[first])*WINDOW_ROWS
                row_end=min(len(y),row_start+WINDOW_ROWS)
                raw=np.asarray(cmi[row_start:row_end,:]); quality=np.asarray(dqf[row_start:row_end,:])
                peak_window=max(peak_window,raw.nbytes+quality.nbytes); windows+=1
                raw=raw[rows[points]-row_start,columns[points]]
                quality=quality[rows[points]-row_start,columns[points]]
                source_lon,source_lat=reverse.transform(x[columns[points]]*height,y[rows[points]]*height)
                navigable=np.isfinite(source_lon)&np.isfinite(source_lat)
                source_zenith=_zenith(source_lon,source_lat,a,b,height,lon0)
                flags=np.zeros(len(points),dtype='u1')
                flags[~navigable]=1
                flags[navigable & ((source_zenith>75)|(quality!=0))]=3
                missing=(raw==cmi.getncattr('_FillValue'))|(quality==dqf.getncattr('_FillValue'))|(quality==3)
                flags[navigable & missing]=2
                # Signed storage with _Unsigned must be viewed before unpacking.
                unsigned=raw.view(np.dtype(f'u{raw.dtype.itemsize}')) if getattr(cmi,'_Unsigned','false')=='true' and raw.dtype.kind=='i' else raw
                limits=cmi.getncattr('valid_range')
                flags[navigable & ~missing & ((unsigned<limits[0])|(unsigned>limits[1]))]=3
                values=unsigned.astype('f8')*float(cmi.scale_factor)+float(cmi.add_offset)
                flags[(flags==0)&~np.isfinite(values)]=2
                old=mask.ravel()[points]
                # Coverage remains unknown; missing outranks other quality causes.
                merged=np.where((old==1)|(flags==1),1,np.where((old==2)|(flags==2),2,np.maximum(old,flags)))
                mask.ravel()[points]=merged
                result.ravel()[points]+=np.where(flags==0,values*weights[points],0)
    result[mask!=0]=0
    return result,mask,{'supported':True,'window_rows':WINDOW_ROWS,'windows_read':windows,'max_raw_window_bytes':peak_window,'source_width':len(x),'source_height':len(y)}


def normalize_satellite(capture: CaptureManifest,destination: Path) -> ProductArtifact:
    if capture.source!='goes19-c13' or len(capture.objects)!=1:
        raise ValueError('expected one GOES-19 C13 capture object')
    receipt=capture_manifest_path(capture)
    with Dataset(object_path(capture,capture.objects[0])) as dataset:
        expanded=_expanded_bytes(dataset)
        cmi=dataset.variables['CMI']
        if cmi.units!='K' or cmi.grid_mapping!='goes_imager_projection' or int(dataset.variables['band_id'][0])!=13 or dataset.platform_ID!='G19':
            raise ValueError('expected GOES-19 C13 brightness temperature in K')
        start=_timestamp(dataset.time_coverage_start); end=_timestamp(dataset.time_coverage_end)
        if start>end: raise ValueError('incoherent satellite scan interval')
        projection=dataset.variables['goes_imager_projection']
        values,mask,allocation=_regrid(dataset,projection)
        navigation={key:projection.getncattr(key) for key in ('grid_mapping_name','sweep_angle_axis','perspective_point_height','semi_major_axis','semi_minor_axis','longitude_of_projection_origin','latitude_of_projection_origin')}
        scene=dataset.scene_id
        sensor={'platform':dataset.platform_ID,'instrument':dataset.instrument_type,'band':13}
    descriptor = {
        "schema": "aviation-weather-v1",
        "representation": "latlon-grid-v1",
        "diagnostic": True,
        "normalization_version": NORMALIZATION_VERSION,
        "source_id": "noaa-goes19-abi",
        "layer_id": "goes19-c13-brightness-temperature",
        "product_type": "satellite-brightness-temperature",
        "capture_manifest_path": str(receipt),
        "attribution": list(capture.attribution),
        "sensor": sensor,
        "time_kind": "observation",
        "method_kind": "sensor",
        "validity_kind": "instant",
        "valid_at_ms": end,
        "valid_from_ms": None,
        "valid_to_ms": None,
        "scan_start_ms": start,
        "scan_end_ms": end,
        "observed_at_ms": end,
        "issued_at_ms": None,
        "run_at_ms": None,
        "lead_seconds": None,
        "retrieved_at_ms": capture.captured_at_ms,
        "generated_at_ms": round(time.time() * 1000),
        "region_intervals": [
            {"region": scene, "scan_start_ms": start, "scan_end_ms": end}
        ],
        "vertical": {
            "kind": "radiometric",
            "reference": "top-of-atmosphere",
            "derivation": "native-brightness-temperature",
        },
        "coverage": {
            "kind": "geostationary-scan",
            "region": scene,
            "missing": "mask",
            "interpolation": "bilinear-nonzero-contributors-valid",
        },
        "quality_policy": {
            "accepted_dqf": [0],
            "maximum_view_zenith_degrees": 75,
            "off_earth_mask": 1,
            "fill_mask": 2,
            "rejected_mask": 3,
            "parallax_correction": False,
        },
        "provenance": {
            "source_objects": [
                {"sha256": o.sha256, "byte_size": o.byte_size, "url": o.url}
                for o in capture.objects
            ],
            "source_navigation": navigation,
            "expanded_object_bytes": expanded,
            "decoder_allocation": allocation,
        },
        "grid": {
            "width": 720,
            "height": 361,
            "longitude_start": -180,
            "longitude_step": 0.5,
            "latitude_start": 90,
            "latitude_step": -0.5,
        },
        "components": {
            "t": {
                "quantity": "brightness-temperature",
                "units": "K",
                "offset": 273.15,
                "scale": 0.01,
            }
        },
    }
    return write_grid(descriptor,{'t':values},mask,destination)
