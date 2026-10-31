"""Deterministic normalized 2D Lorentz dynamics with a Boris velocity rotation."""
import numpy as np

DT = 1 / 240
DURATION = 8
SOFTENING = .065
ELECTRIC_K = .018
MAGNETIC_B = 5.0
MAGNETIC_SIGMA = .16
SPEED = .28
MAX_SPEED = 1.4
REACTOR_RADIUS = .031
PROTECTED_RADIUS = .105


def reactors(count):
    return {2: [(.12,.5),(.88,.5)], 3: [(.12,.5),(.78,.18),(.78,.82)],
            4: [(.12,.18),(.88,.18),(.88,.82),(.12,.82)]}[count]


def fields(position, generators):
    e = np.zeros(2); b = 0.
    for g in generators:
        d = position - np.array([g['x'], g['y']]); r2 = np.dot(d,d)
        if g['kind'] == 'coil':
            b += MAGNETIC_B * np.exp(-r2/(2*MAGNETIC_SIGMA**2))
        else:
            e += ELECTRIC_K * (1 if g['kind']=='positive' else -1) * d / (r2+SOFTENING**2)**1.5
    norm = np.linalg.norm(e)
    if norm > 3: e *= 3/norm
    return e, float(np.clip(b,-20,20))


def boris(position, velocity, generators, dt=DT):
    e,b = fields(position, generators)
    minus = velocity + e*dt/2
    t = b*dt/2; s = 2*t/(1+t*t)
    prime = minus + np.array([minus[1], -minus[0]])*t
    plus = minus + np.array([prime[1], -prime[0]])*s
    v = plus + e*dt/2
    speed = np.linalg.norm(v)
    if speed > MAX_SPEED: v *= MAX_SPEED/speed
    return position + v*dt, v


def swept(a,b,center,radius=REACTOR_RADIUS):
    d=b-a; length=np.dot(d,d)
    t=np.clip(np.dot(np.array(center)-a,d)/length,0,1) if length else 0
    return np.linalg.norm(a+t*d-np.array(center)) <= radius


def simulate_numpy(players):
    centers=reactors(len(players)); generators=[g for p in players for g in p['generators']]
    positions=[]; velocities=[]
    for p,c in zip(players,centers):
        direction=np.array([np.cos(p['angle']), np.sin(p['angle'])])
        positions.append(np.array(c)+direction*.046); velocities.append(direction*SPEED)
    alive=[True]*len(players); frames=[]; events=[]
    for step in range(int(DURATION/DT)+1):
        if step%8==0: frames.append([[float(x) for x in p] if alive[i] else None for i,p in enumerate(positions)])
        for i in range(len(players)):
            if not alive[i]: continue
            old=positions[i].copy(); positions[i],velocities[i]=boris(old,velocities[i],generators)
            hits=[]
            for j,c in enumerate(centers):
                if swept(old,positions[i],c):
                    hits.append((np.linalg.norm(np.array(c)-old),j))
            if hits:
                j=min(hits)[1]; alive[i]=False
                events.append({'owner':players[i]['id'],'target':players[j]['id'],'scored':i!=j,'time':step*DT,'x':float(positions[i][0]),'y':float(positions[i][1])})
            elif np.any(positions[i]<0) or np.any(positions[i]>1): alive[i]=False
    return {'frames':frames,'events':events,'frame_dt':8*DT,'duration':DURATION}


def simulate(players):
    """JAX is the default. NumPy is available only through explicit configuration."""
    import os
    if os.getenv('PHYSICS_ENGINE', 'jax') == 'numpy':
        return simulate_numpy(players)
    from .jax_engine import simulate_jax
    return simulate_jax(players)
