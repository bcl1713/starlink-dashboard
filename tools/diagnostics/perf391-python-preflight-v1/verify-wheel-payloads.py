import hashlib, importlib.metadata as m, json, pathlib, urllib.request, zipfile
out=pathlib.Path('/tmp/perf391-python-preflight/wheels'); out.mkdir(exist_ok=True)
rows=[]
for d in m.distributions():
    name=d.metadata['Name']; version=d.version
    tags=[x[5:] for x in d.read_text('WHEEL').splitlines() if x.startswith('Tag: ')]
    data=json.load(urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json',timeout=20))
    choices=[x for x in data['urls'] if x['filename'].endswith('.whl') and any(t == '-'.join(x['filename'][:-4].split('-')[-3:-1]+[plat]) for plat in x['filename'][:-4].split('-')[-1].split('.') for t in tags)]
    assert len(choices)==1,(name,tags)
    x=choices[0]; blob=urllib.request.urlopen(x['url'],timeout=30).read(); sha=hashlib.sha256(blob).hexdigest()
    assert sha==x['digests']['sha256']
    lock=pathlib.Path('tools/diagnostics/perf391-python-preflight-v1/requirements.lock').read_text(); assert sha in lock
    p=out/x['filename']; p.write_bytes(blob)
    with zipfile.ZipFile(p) as z:
        for f in d.files:
            s=str(f)
            if s in z.namelist() and not s.endswith('/RECORD'):
                assert d.locate_file(f).read_bytes()==z.read(s),s
    rows.append({'name':name,'version':version,'filename':x['filename'],'sha256':sha,'url':x['url'],'installed_payload_matches_wheel':True})
pathlib.Path('tools/diagnostics/perf391-python-preflight-v1/evidence/wheels.json').write_text(json.dumps(rows,indent=2)+'\n')
