# -*- coding: utf-8 -*-
import sys, re
sys.path.insert(0, r'<repo>\tools')
from cx import make_session

s = make_session()
url = ('https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId=586200478&courseId=226942553'
       '&clazzid=153630595&cpi=580767375&enc=fe5966a5c14c8478375c1e3808dfdf77&mooc2=1&hidetype=0&fanyaVersion=0')
t = s.get(url, timeout=25).text
print('LEN', len(t))
print('has 000d181f:', '000d181f40bb48a2908a6326641d79ce' in t)
seen = {}
for m in re.finditer(r'[0-9a-f]{32}', t):
    v = m.group(0)
    if v in seen:
        continue
    seen[v] = t[max(0, m.start() - 90):m.start()].replace('\n', ' ')
for v, pre in seen.items():
    print(v, '<<<', pre[-90:])
