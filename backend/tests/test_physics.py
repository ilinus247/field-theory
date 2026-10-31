import numpy as np
from app.physics.simulation import fields,boris,swept,simulate

def test_electric_signs():
    g={'kind':'positive','x':.5,'y':.5}; e,_=fields(np.array([.7,.5]),[g]); assert e[0]>0
    g['kind']='negative'; e,_=fields(np.array([.7,.5]),[g]); assert e[0]<0

def test_magnetic_energy_and_curve():
    p=np.array([.5,.5]); v=np.array([.2,0.]); g=[{'kind':'coil','x':.5,'y':.5}]
    p2,v2=boris(p,v,g); assert v2[1]<0
    for _ in range(1920): p,v=boris(p,v,g)
    assert abs(np.linalg.norm(v)-.2)<1e-10
    assert np.isfinite(p).all()

def test_swept_fast_particle():
    assert swept(np.array([0.,.5]),np.array([1.,.5]),(.5,.5))
    assert not swept(np.array([0.,0.]),np.array([1.,0.]),(.5,.5))

def test_deterministic_and_hit():
    ps=[{'id':'a','angle':0.,'generators':[]},{'id':'b','angle':np.pi,'generators':[]}]
    a=simulate(ps); b=simulate(ps); assert a==b
    assert len(a['events'])==2 and all(e['scored'] for e in a['events'])
    assert len(a['frames'])==241

def test_extreme_fields_finite():
    gs=[{'kind':k,'x':.5,'y':.5} for k in ['positive','negative','coil']]*3
    p=np.array([.5,.5]);v=np.array([1.,1.])
    for _ in range(1920): p,v=boris(p,v,gs)
    assert np.isfinite(p).all() and np.isfinite(v).all()
