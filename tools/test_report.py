# -*- coding: utf-8 -*-
"""验证 video 进度上报接口。playingTime 用当前 headOffset，先不改动学习进度。"""
import sys, json, time, hashlib
sys.path.insert(0, r'<repo>\tools')
from cx import make_session

SALT = 'd_yHJ!$pdA~5'
def enc_of(clazzid, userid, jobid, objectid, playing_ms, duration_ms, clip):
    s = f'[{clazzid}][{userid}][{jobid}][{objectid}][{playing_ms}][{SALT}][{duration_ms}][{clip}]'
    return hashlib.md5(s.encode()).hexdigest()

s = make_session()
clazzid, courseid, cpi = '153630595', '226942553', '000000000'
userid = '123456789'
obj = '2b4b6ddfa1f17f4e330d828ea1f3b94e'
jobid = '1662169846944338'
duration = 589
playing = 44000 // 1000  # 44s, 与当前 headOffset 一致
clip = f'0_{duration}'
e = enc_of(clazzid, userid, jobid, obj, playing * 1000, duration * 1000, clip)
print('enc =', e)

q = {
    'clazzId': clazzid, 'playingTime': str(playing), 'duration': str(duration),
    'clipTime': clip, 'objectId': obj,
    'otherInfo': f'nodeId_586200478-cpi_{cpi}-rt_d-ds_0-ff_1-be_0_{duration}-vt_1-v_6-enc_b9eec3e995729661dc5da6b4c2c915c7',
    'courseId': courseid, 'jobid': jobid, 'userid': userid, 'isdrag': '3', 'view': 'pc',
    'enc': e, 'rt': '0.9', 'videoFaceCaptureEnc': '', 'dtype': 'Video',
    '_t': str(int(time.time() * 1000)), 'attDuration': str(duration),
    'attDurationEnc': '94e9a6aa23d57341f7f40f16f2329733', 'courseEngineInfo': 'false',
}
ref = f'https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=586200478&courseId={courseid}&clazzid={clazzid}&cpi={cpi}&enc=fe5966a5c14c8478375c1e3808dfdf77&mooc2=1'

def try_variant(label, path):
    url = 'https://mooc1.chaoxing.com' + path
    try:
        r = s.get(url, params=q, timeout=25, headers={'Referer': ref, 'X-Requested-With': 'XMLHttpRequest'})
        print(f'[{label}] {r.status_code} len={len(r.text)} body={r.text[:220]!r}')
    except Exception as ex:
        print(f'[{label}] ERR {ex}')

try_variant('A no-enc', f'/mooc-ans/multimedia/log/a/{cpi}')
try_variant('B report-enc', f'/mooc-ans/multimedia/log/a/{cpi}/000d181f40bb48a2908a6326641d79ce')
try_variant('C studentstudy-enc', f'/mooc-ans/multimedia/log/a/{cpi}/fe5966a5c14c8478375c1e3808dfdf77')
