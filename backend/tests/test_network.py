import time
from fastapi.testclient import TestClient
from app.main import app,rooms

ORIGIN={'origin':'http://localhost:5173'}
def receive_state(ws,phase=None):
    while True:
        msg=ws.receive_json()
        if msg['type']=='state' and (phase is None or msg['state']['phase']==phase):return msg['state']

def test_websocket_match_reconnect_and_independent_rooms():
    rooms.clear()
    with TestClient(app) as client:
        with client.websocket_connect('/ws',headers=ORIGIN) as a,client.websocket_connect('/ws',headers=ORIGIN) as b:
            a.send_json({'type':'create','name':'ada'});identity=a.receive_json();first=receive_state(a);code=first['code']
            b.send_json({'type':'join','name':'ben','code':code});bid=b.receive_json();receive_state(b);receive_state(a)
            with client.websocket_connect('/ws',headers=ORIGIN) as other:
                other.send_json({'type':'create','name':'third'});other.receive_json();os=receive_state(other);assert os['code']!=code
            a.send_json({'type':'start'});receive_state(a,'construction');receive_state(b,'construction')
            for number in range(1,6):
                for ws,angle in [(a,0),(b,3.141592653589793)]:ws.send_json(dict(type='ready',round=number,angle=angle,generators=[]))
                sa=receive_state(a,'simulation');sb=receive_state(b,'simulation');assert sa['playback']==sb['playback'];assert sa['round']==number
                rooms[code].deadline=time.time()-.1
                ra=receive_state(a,'results');rb=receive_state(b,'results');assert ra['players']==rb['players'];assert ra['players'][0]['score']==number
                rooms[code].deadline=time.time()-.1
                phase='finished' if number==5 else 'construction';receive_state(a,phase);final=receive_state(b,phase)
            assert final['players'][0]['score']==final['players'][1]['score']==5
            a.send_json({'type':'rematch'});receive_state(a,'construction');receive_state(b,'construction')
            with client.websocket_connect('/ws',headers=ORIGIN) as refreshed:
                refreshed.send_json(dict(type='join',code=code,name='ada',token=identity['token']));newid=refreshed.receive_json();assert newid['id']==identity['id'];s=receive_state(refreshed);assert len(s['players'])==2
                refreshed.send_json(dict(type='ready',round=0,angle=0,generators=[]));assert refreshed.receive_json()['type']=='error'
                refreshed.send_text('{broken');assert refreshed.receive_json()['type']=='error'
                refreshed.send_text('[]');assert refreshed.receive_json()['type']=='error'

def test_bad_code_and_origin():
    with TestClient(app) as c:
        with c.websocket_connect('/ws',headers=ORIGIN) as ws:
            ws.send_json(dict(type='join',name='a',code='XXXXX'));assert 'not found' in ws.receive_json()['message']
