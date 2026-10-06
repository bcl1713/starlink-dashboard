"""Independent geographic CPU reference, with no renderer/normalizer helpers.

Longitude bracketing uses sorted geographic coordinates on three adjacent worlds;
latitude uses sorted geographic nodes. Source checks select exact nodes from
ecCodes coordinate arrays, independently of scan ordering/regridding.
"""

import json
import math
from pathlib import Path

import eccodes as ec
import numpy as np

from .model import CaptureManifest, confined, file_hash, object_path


DEFAULT_GFS_COORDINATES = (
    (-180, 0), (179.5, 10), (-179.5, -10), (0, 89.5), (120, -89.5),
    (0, 90), (-180, -90), (-45, 50), (135, -35), (30, 20),
)


def _bracket(coordinates, query, *, descending=False):
    """Keep an enclosing two-node stencil even when one weight is zero."""
    ordered = sorted(coordinates, reverse=descending)
    for (first, first_index), (second, second_index) in zip(ordered, ordered[1:]):
        enclosed = second < query <= first if descending else first <= query < second
        if enclosed:
            fraction = (query - first) / (second - first)
            return [(first_index, 1 - fraction), (second_index, fraction)]
    # The end of partial coverage or a latitude pole clamps both corners to
    # that boundary node. Full-world longitude has shifted geographic nodes.
    if ordered and query == ordered[-1][0]:
        return [(ordered[-1][1], 1.0), (ordered[-1][1], 0.0)]
    raise ValueError("reference coordinate outside grid coverage")


def sample_grid(descriptor_path: Path, longitude: float, latitude: float) -> dict:
    """Read verified normalized buffers and bracket geographic nodes independently.

    This reusable oracle accepts arbitrary geographic samples for future actual
    shader readback. It never receives browser UV/index calculations as input.
    """
    descriptor_path = Path(descriptor_path)
    descriptor = json.loads(descriptor_path.read_text())
    if descriptor["schema"] != "aviation-weather-v1" or descriptor["representation"] != "latlon-grid-v1":
        raise ValueError("unsupported reference schema")
    if not math.isfinite(longitude) or not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("invalid reference geographic coordinate")
    grid = descriptor["grid"]
    width, height = grid["width"], grid["height"]
    base_lons = [grid["longitude_start"] + i * grid["longitude_step"] for i in range(width)]
    lats = [(grid["latitude_start"] + i * grid["latitude_step"], i) for i in range(height)]
    # Geographic equivalence, not an integer longitude-to-texture formula.
    longitude = math.remainder(longitude, 360)
    if longitude < base_lons[0]:
        longitude += 360
    if longitude >= base_lons[0] + 360:
        longitude -= 360
    full_longitude = math.isclose(width * grid["longitude_step"], 360)
    if (not full_longitude and not base_lons[0] <= longitude <= base_lons[-1]) or not min(coordinate for coordinate, _ in lats) <= latitude <= max(coordinate for coordinate, _ in lats):
        return {"longitude": longitude, "latitude": latitude, "mask": 1,
                "values": {name: None for name in descriptor["components"]}, "contributors": []}
    shifts = (-360, 0, 360) if full_longitude else (0,)
    candidates = [(coordinate + shift, index) for shift in shifts for index, coordinate in enumerate(base_lons)]
    xs = _bracket(candidates, longitude)
    ys = _bracket(lats, latitude, descending=grid["latitude_step"] < 0)
    arrays = {}
    for name, item in {**descriptor["components"], "mask": descriptor["mask"]}.items():
        path = confined(descriptor_path.parent, item["path"])
        if path.stat().st_size != item["byte_size"] or file_hash(path) != item["sha256"]:
            raise ValueError("reference artifact changed")
        array = np.fromfile(path, dtype="u1" if name == "mask" else "<i2")
        if len(array) != width * height:
            raise ValueError("reference payload dimension mismatch")
        arrays[name] = array.reshape(height, width)
    stencil = [(y, x, wy * wx) for y, wy in ys for x, wx in xs]
    masks = [int(arrays["mask"][y, x]) for y, x, _ in stencil]
    invalid = next((value for value in masks if value != 0), 0)
    contributing = [(y, x, weight) for y, x, weight in stencil if weight > 0]
    values = {}
    for name, declaration in descriptor["components"].items():
        values[name] = None if invalid else sum(
            (declaration["offset"] + declaration["scale"] * int(arrays[name][y, x])) * weight
            for y, x, weight in contributing
        )
    return {"longitude": longitude, "latitude": latitude, "mask": invalid, "values": values,
            "contributors": [{"longitude": base_lons[x], "latitude": lats[y][0], "weight": weight} for y, x, weight in contributing]}


def compare_gfs(capture: CaptureManifest, descriptor_path: Path, coordinates=DEFAULT_GFS_COORDINATES) -> list[dict]:
    """Retain exact source-node comparisons; non-source-node queries fail explicitly.

    These controls deliberately coincide with output and source nodes, so source
    resampling tolerance is zero. Quantization tolerance is half a declared step.
    Off-node renderer controls use sample_grid without claiming source equality.
    """
    descriptor = json.loads(Path(descriptor_path).read_text())
    records = [{"longitude": lon, "latitude": lat, "source_values": {}, "source_coordinates": {},
                "source_metadata": {}, "source_hashes": {}, "normalized_values": sample_grid(descriptor_path, lon, lat)["values"],
                "normalized_mask": sample_grid(descriptor_path, lon, lat)["mask"],
                "resampling_tolerance": {}, "resampling_error": {}, "quantization_tolerance": {}, "absolute_error": {}}
               for lon, lat in coordinates]
    for obj in capture.objects:
        with object_path(capture, obj).open("rb", buffering=0) as stream:
            if stream.read(4) != b"GRIB":
                continue
            stream.seek(0)
            handle = ec.codes_grib_new_from_file(stream)
            if handle is None:
                raise ValueError("reference source message absent")
            try:
                name = ec.codes_get(handle, "shortName")
                metadata = {key: ec.codes_get(handle, key) for key in ("gridType", "Ni", "Nj", "units", "typeOfLevel", "level", "dataDate", "dataTime", "endStep", "validityDate", "validityTime", "iScansNegatively", "jScansPositively", "uvRelativeToGrid")}
                source_lats = ec.codes_get_array(handle, "latitudes")
                source_lons = ec.codes_get_array(handle, "longitudes")
                source_values = ec.codes_get_values(handle)
                for record in records:
                    # Geodesic nearest-point routines can pick ANY longitude at
                    # a pole. Preserve the exact declared node longitude.
                    delta_lon = np.abs(source_lons - record["longitude"])
                    equivalent_lon = np.minimum(delta_lon, np.abs(delta_lon - 360))
                    matches = np.flatnonzero((equivalent_lon < 1e-7) & (np.abs(source_lats - record["latitude"]) < 1e-7))
                    if len(matches) != 1:
                        raise ValueError("source oracle control must be an exact unique source node")
                    index = int(matches[0])
                    value = float(source_values[index])
                    normalized = record["normalized_values"][name]
                    if record["normalized_mask"] != 0 or normalized is None:
                        raise ValueError("source comparison control is missing")
                    error = abs(value - normalized)
                    tolerance = descriptor["components"][name]["scale"] / 2
                    if error > tolerance + 1e-9:
                        raise ValueError("independent source/reference mismatch")
                    record["source_values"][name] = value
                    record["source_coordinates"][name] = {"longitude": float(source_lons[index]), "latitude": float(source_lats[index]), "source_index": index}
                    record["source_metadata"][name] = metadata
                    record["source_hashes"][name] = obj.sha256
                    record["absolute_error"][name] = error
                    record["resampling_error"][name] = 0.0
                    record["resampling_tolerance"][name] = 0.0
                    record["quantization_tolerance"][name] = tolerance
            finally:
                ec.codes_release(handle)
    if any(set(record["source_values"]) != {"u", "v", "t"} for record in records):
        raise ValueError("independent source controls incomplete")
    return records


DEFAULT_SATELLITE_COORDINATES = (
    (-75, 0), (-80, 10), (-100, 20), (-60, 30), (-90, 40),
    (-50, -10), (-65, -25), (-100, -30), (-120, 5), (-35, 15),
)


def compare_satellite(capture: CaptureManifest, descriptor_path: Path,
                      coordinates=DEFAULT_SATELLITE_COORDINATES) -> list[dict]:
    """Independent NOAA PUG ellipsoid/scan-angle source and normalized checks.

    Uses analytic Earth/satellite vectors, not PROJ or normalizer coordinate
    helpers. Controls are exact geographic output nodes. Each record compares
    the source bilinear value to the normalized buffer, while reporting the
    difference from the nearest source pixel separately as a local resampling
    measurement. That local difference is not a global reconstruction bound.
    """
    from datetime import datetime
    from netCDF4 import Dataset

    descriptor_path=Path(descriptor_path)
    descriptor=json.loads(descriptor_path.read_text())
    if capture.source!='goes19-c13' or len(capture.objects)!=1:
        raise ValueError('satellite reference requires GOES-19 C13 capture')
    obj=capture.objects[0]
    if descriptor['provenance']['source_objects'][0]['sha256']!=obj.sha256:
        raise ValueError('satellite reference provenance differs')
    records=[]
    with Dataset(object_path(capture,obj)) as dataset:
        projection=dataset.variables['goes_imager_projection']
        if projection.grid_mapping_name!='geostationary' or projection.sweep_angle_axis!='x' or projection.latitude_of_projection_origin!=0:
            raise ValueError('reference requires supported GOES fixed grid')
        a=float(projection.semi_major_axis); b=float(projection.semi_minor_axis)
        h=float(projection.perspective_point_height)+a
        lon0=math.radians(float(projection.longitude_of_projection_origin))
        e2=1-(b/a)**2
        x=np.asarray(dataset.variables['x'][:],dtype='f8')
        y=np.asarray(dataset.variables['y'][:],dtype='f8')
        xnodes=sorted((float(value),index) for index,value in enumerate(x))
        ynodes=sorted((float(value),index) for index,value in enumerate(y))
        cmi=dataset.variables['CMI']; dqf=dataset.variables['DQF']
        cmi.set_auto_maskandscale(False); dqf.set_auto_maskandscale(False)
        for field,attribute in [('scan_start_ms','time_coverage_start'),('scan_end_ms','time_coverage_end')]:
            ms=round(datetime.fromisoformat(dataset.getncattr(attribute).replace('Z','+00:00')).timestamp()*1000)
            if descriptor[field]!=ms:
                raise ValueError('satellite reference scan interval differs')
        for longitude,latitude in coordinates:
            # Controls must hit published grid nodes; no browser texture math.
            grid=descriptor['grid']
            if longitude not in [grid['longitude_start']+i*grid['longitude_step'] for i in range(grid['width'])] or latitude not in [grid['latitude_start']+i*grid['latitude_step'] for i in range(grid['height'])]:
                raise ValueError('source comparison requires exact geographic output nodes')
            lat=math.radians(latitude); lon=math.radians(longitude)-lon0
            radius=a/math.sqrt(1-e2*math.sin(lat)**2)
            ex=radius*math.cos(lat)*math.cos(lon)
            ey=radius*math.cos(lat)*math.sin(lon)
            ez=radius*(1-e2)*math.sin(lat)
            sx=h-ex
            distance=math.sqrt(sx*sx+ey*ey+ez*ez)
            scan_x=math.asin(ey/distance); scan_y=math.atan2(ez,sx)
            cosine=(sx*math.cos(lat)*math.cos(lon)-ey*math.cos(lat)*math.sin(lon)-ez*math.sin(lat))/distance
            zenith=math.degrees(math.acos(max(-1,min(1,cosine))))
            if zenith>75:
                raise ValueError('satellite control outside conservative zenith policy')
            xs=_bracket(xnodes,scan_x); ys=_bracket(ynodes,scan_y)
            contributors=[]
            for row,wy in ys:
                for column,wx in xs:
                    weight=wx*wy
                    if weight<=0: continue
                    raw=int(cmi[row,column]); quality=int(dqf[row,column])
                    if raw==int(cmi.getncattr('_FillValue')) or quality!=0:
                        raise ValueError('satellite control has missing/rejected source contributor')
                    if getattr(cmi,'_Unsigned','false')=='true' and raw<0:
                        raw+=1<<(8*cmi.dtype.itemsize)
                    minimum,maximum=cmi.valid_range
                    if not minimum<=raw<=maximum:
                        raise ValueError('satellite source value outside valid range')
                    value=raw*float(cmi.scale_factor)+float(cmi.add_offset)
                    # NOAA PUG ray/ellipsoid intersection, independent of PROJ.
                    xx=float(x[column]); yy=float(y[row])
                    aa=math.sin(xx)**2+math.cos(xx)**2*(math.cos(yy)**2+(a/b)**2*math.sin(yy)**2)
                    bb=-2*h*math.cos(xx)*math.cos(yy)
                    cc=h*h-a*a
                    discriminant=bb*bb-4*aa*cc
                    if discriminant<0: raise ValueError('off-Earth source contributor')
                    ray=(-bb-math.sqrt(discriminant))/(2*aa)
                    vx=h-ray*math.cos(xx)*math.cos(yy)
                    vy=ray*math.sin(xx)
                    vz=ray*math.cos(xx)*math.sin(yy)
                    source_lat=math.atan((a/b)**2*vz/math.hypot(vx,vy))
                    source_lon=lon0+math.atan2(vy,vx)
                    n=a/math.sqrt(1-e2*math.sin(source_lat)**2)
                    rx=n*math.cos(source_lat)*math.cos(source_lon-lon0)
                    ry=n*math.cos(source_lat)*math.sin(source_lon-lon0)
                    rz=n*(1-e2)*math.sin(source_lat)
                    dx=h-rx; magnitude=math.sqrt(dx*dx+ry*ry+rz*rz)
                    back_x=math.asin(ry/magnitude); back_y=math.atan2(rz,dx)
                    normal_dot=(dx*math.cos(source_lat)*math.cos(source_lon-lon0)-ry*math.cos(source_lat)*math.sin(source_lon-lon0)-rz*math.sin(source_lat))/magnitude
                    source_zenith=math.degrees(math.acos(max(-1,min(1,normal_dot))))
                    if source_zenith>75: raise ValueError('source contributor exceeds zenith policy')
                    contributors.append({'row':row,'column':column,'scan_x_rad':xx,'scan_y_rad':yy,
                        'longitude':math.degrees(source_lon),'latitude':math.degrees(source_lat),
                        'navigation_roundtrip_error_rad':max(abs(back_x-xx),abs(back_y-yy)),
                        'view_zenith_degrees':source_zenith,'packed_value':raw,'dqf':quality,'value_K':value,'weight':weight})
            regridded=sum(point['value_K']*point['weight'] for point in contributors)
            nearest=min(contributors,key=lambda point:(point['scan_x_rad']-scan_x)**2+(point['scan_y_rad']-scan_y)**2)
            source_values=[point['value_K'] for point in contributors]
            normalized=sample_grid(descriptor_path,longitude,latitude)
            normalized_value=normalized['values']['t']
            if normalized['mask']!=0 or normalized_value is None:
                raise ValueError('satellite control has invalid normalized stencil')
            tolerance=descriptor['components']['t']['scale']/2
            quantization_error=abs(normalized_value-regridded)
            if quantization_error>tolerance+1e-7:
                raise ValueError('satellite source-to-normalized quantization comparison failed')
            records.append({'longitude':longitude,'latitude':latitude,'source_hash':obj.sha256,
                'scan_start_ms':descriptor['scan_start_ms'],'scan_end_ms':descriptor['scan_end_ms'],
                'target_scan_x_rad':scan_x,'target_scan_y_rad':scan_y,'target_view_zenith_degrees':zenith,
                'source_contributors':contributors,'nearest_source_value':nearest['value_K'],
                'regridded_value':regridded,'normalized_value':normalized_value,'normalized_mask':normalized['mask'],
                'resampling_error':abs(regridded-nearest['value_K']),
                'resampling_local_range_bound':max(source_values)-min(source_values),
                'resampling_claim':'local bilinear-versus-nearest difference; no global accuracy claim',
                'quantization_tolerance':tolerance,'quantization_error':quantization_error})
    return records
