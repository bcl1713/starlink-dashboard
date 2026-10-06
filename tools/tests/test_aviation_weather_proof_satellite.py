"""Small real NetCDF fixtures expose navigation, quality and scan mistakes."""
import importlib
import json
from pathlib import Path

import numpy as np
from netCDF4 import Dataset
import pytest

from acceptance.aviation_weather_proof.model import CaptureManifest, CapturedObject, file_hash, load_capture, write_manifest


def source(tmp_path, *, start='2026-10-06T00:00:20.9Z', end='2026-10-06T00:09:52.8Z', scene='Full Disk', values=None, quality=None, sweep='x'):
    tmp_path.mkdir(exist_ok=True)
    path = tmp_path / 'source.nc'
    with Dataset(path, 'w') as d:
        d.createDimension('x', 2); d.createDimension('y', 2); d.createDimension('band', 1)
        d.time_coverage_start=start; d.time_coverage_end=end
        d.platform_ID='G19'; d.instrument_type='ABI'; d.scene_id=scene
        x=d.createVariable('x','f8',('x',)); x.units='rad'; x[:]=[-.01,.01]
        y=d.createVariable('y','f8',('y',)); y.units='rad'; y[:]=[.01,-.01]
        p=d.createVariable('goes_imager_projection','i4')
        p.grid_mapping_name='geostationary'; p.sweep_angle_axis=sweep
        p.perspective_point_height=35786023.; p.semi_major_axis=6378137.; p.semi_minor_axis=6356752.31414
        p.latitude_of_projection_origin=0.; p.longitude_of_projection_origin=-75.
        b=d.createVariable('band_id','i4',('band',)); b[:]=13
        c=d.createVariable('CMI','i2',('y','x'),fill_value=-1)
        c.units='K'; c.grid_mapping='goes_imager_projection'; c.scale_factor=.5; c.add_offset=200.; c.valid_range=np.array([0,4095],dtype='i2'); c._Unsigned='true'
        c.set_auto_maskandscale(False); c[:]=np.full((2,2),100,dtype='i2') if values is None else values
        q=d.createVariable('DQF','i1',('y','x'),fill_value=-1); q._Unsigned='true'
        q.set_auto_maskandscale(False); q[:]=np.zeros((2,2),dtype='i1') if quality is None else quality
    manifest=CaptureManifest('goes19-c13',1791245500000,(CapturedObject('https://noaa-goes19.s3.amazonaws.com/fixture.nc',None,'source.nc',file_hash(path),path.stat().st_size),),('NOAA',))
    write_manifest(manifest,tmp_path/'capture.json')
    return load_capture(tmp_path/'capture.json')


def normalize(capture, destination):
    module=importlib.import_module('acceptance.aviation_weather_proof.satellite')
    return module.normalize_satellite(capture,destination)


def decoded(artifact):
    d=json.loads(artifact.descriptor_path.read_text()); shape=(361,720)
    return d,np.fromfile(artifact.descriptor_path.parent/'t.bin',dtype='<i2').reshape(shape),np.fromfile(artifact.descriptor_path.parent/'mask.bin',dtype='u1').reshape(shape)


def test_scale_and_quality_flags(tmp_path):
    # Incorrect auto-scaling twice, dropped fills, or acceptance of DQF!=0 breaks this.
    for name,values,quality,want in [('good',None,None,0),('fill',[[-1,-1],[-1,-1]],None,2),('dqf',None,[[1,1],[1,1]],3),('dqf_fill',None,[[-1,-1],[-1,-1]],2),('no_value',None,[[3,3],[3,3]],2)]:
        artifact=normalize(source(tmp_path/name,values=values,quality=quality),tmp_path/f'{name}-product')
        d,t,mask=decoded(artifact)
        assert mask[180,210] == want # nadir: -75 longitude, 0 latitude
        if want==0: assert d['components']['t']['offset']+d['components']['t']['scale']*t[180,210] == pytest.approx(250,abs=.005)
        else: assert t[180,210] == 0


def test_off_earth_and_limb_mask(tmp_path):
    # Treating invisible points as temperatures or ignoring zenith cutoff breaks this.
    _,_,mask=decoded(normalize(source(tmp_path),tmp_path/'product'))
    assert mask[180,570] == 1 # far side at +105
    assert mask[180,356] == 3 # +73 degrees from nadir, visible but zenith >75
    assert mask[180,210] == 0


def test_scan_interval_survives_identity(tmp_path):
    a=decoded(normalize(source(tmp_path/'a'),tmp_path/'pa'))[0]
    b=decoded(normalize(source(tmp_path/'b',start='2026-10-06T00:00:21.0Z'),tmp_path/'pb'))[0]
    assert a['scan_start_ms']==1791244820900 and a['scan_end_ms']==1791245392800
    assert a['valid_at_ms']==a['scan_end_ms']
    assert a['product_id']==b['product_id'] and a['instance_id']!=b['instance_id']
    assert a['sensor']['band']==13 and a['sensor']['platform']=='G19'
    assert a['components']['t']['quantity']=='brightness-temperature'


def test_region_intervals_not_collapsed(tmp_path):
    a=decoded(normalize(source(tmp_path/'a',scene='Mesoscale 1'),tmp_path/'pa'))[0]
    b=decoded(normalize(source(tmp_path/'b',start='2026-10-06T00:03:00Z',end='2026-10-06T00:04:00Z',scene='Mesoscale 2'),tmp_path/'pb'))[0]
    assert a['region_intervals']==[{'region':'Mesoscale 1','scan_start_ms':1791244820900,'scan_end_ms':1791245392800}]
    assert b['region_intervals']==[{'region':'Mesoscale 2','scan_start_ms':1791244980000,'scan_end_ms':1791245040000}]
    assert a['instance_id']!=b['instance_id']


def test_unsupported_navigation_is_unknown(tmp_path):
    _,_,mask=decoded(normalize(source(tmp_path,sweep='y'),tmp_path/'product'))
    assert np.all(mask==1)


def test_expanded_object_rejected_before_science_allocation(tmp_path):
    c=source(tmp_path)
    # A huge sparse dimension must be rejected without reading its payload.
    with Dataset(tmp_path/'source.nc','a') as d:
        d.createDimension('oversized',40_000_000)
        d.createVariable('expansion','f8',('oversized',),fill_value=False)
    manifest=CaptureManifest(c.source,c.captured_at_ms,(CapturedObject(c.objects[0].url,None,'source.nc',file_hash(tmp_path/'source.nc'),(tmp_path/'source.nc').stat().st_size),),c.attribution)
    write_manifest(manifest,tmp_path/'capture.json')
    with pytest.raises(ValueError,match='expanded'):
        normalize(load_capture(tmp_path/'capture.json'),tmp_path/'product')
    assert not (tmp_path/'product').exists()


def test_independent_source_oracle_retains_navigation_and_separate_errors(tmp_path):
    # Nearest-neighbor substitution instead of bilinear, or comparing a source
    # pixel to itself instead of the published buffer, breaks this literal.
    c=source(tmp_path,values=[[0,100],[200,300]])
    artifact=normalize(c,tmp_path/'product')
    reference=importlib.import_module('acceptance.aviation_weather_proof.reference')
    records=reference.compare_satellite(c,artifact.descriptor_path,coordinates=((-75,0),))
    sample=records[0]
    assert sample['regridded_value']==pytest.approx(275,abs=1e-8)
    assert sample['normalized_value']==pytest.approx(275,abs=.005)
    assert sample['quantization_error']<=.005
    assert sample['resampling_error']>0
    assert len(sample['source_contributors'])==4
    assert sum(point['weight'] for point in sample['source_contributors'])==pytest.approx(1)
    assert all(point['navigation_roundtrip_error_rad']<1e-10 for point in sample['source_contributors'])


@pytest.mark.parametrize('values,quality,want', [
    ([[100,-1],[100,100]],None,2),
    (None,[[0,1],[0,0]],3),
])
def test_invalid_contributor_is_not_filled(tmp_path,values,quality,want):
    _,t,mask=decoded(normalize(source(tmp_path,values=values,quality=quality),tmp_path/'product'))
    assert mask[180,210]==want
    assert t[180,210]==0


def test_off_earth_source_contributors_remain_unknown(tmp_path):
    c=source(tmp_path)
    with Dataset(tmp_path/'source.nc','a') as dataset:
        dataset.variables['x'][:]=[-.151844,.151844]
        dataset.variables['y'][:]=[.151844,-.151844]
    manifest=CaptureManifest(c.source,c.captured_at_ms,(CapturedObject(c.objects[0].url,None,'source.nc',file_hash(tmp_path/'source.nc'),(tmp_path/'source.nc').stat().st_size),),c.attribution)
    write_manifest(manifest,tmp_path/'capture.json')
    _,t,mask=decoded(normalize(load_capture(tmp_path/'capture.json'),tmp_path/'product'))
    assert mask[180,210]==1
    assert t[180,210]==0
