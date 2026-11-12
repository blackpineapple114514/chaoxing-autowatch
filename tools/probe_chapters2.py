# -*- coding: utf-8 -*-
import sys, re, time
sys.path.insert(0, r'<repo>\tools')
from cx import make_session

s = make_session()
courseid, clazzid, cpi = '226942553', '153630595', '000000000'
url = f'https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse?courseid={courseid}&clazzid={clazzid}&cpi={cpi}&ut=s&t={int(time.time()*1000)}'
r = s.get(url, timeout=25, headers={'Referer': 'https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction'})
t = r.text
print('status', r.status_code, 'len', len(t), 'final', r.url[:120])
for k in ['chapterId', 'knowledgeid', 'jobcount', 'chapter', 'objectId', 'data-pid', 'nodeId']:
    i = t.find(k)
    print(f'-- {k} @ {i}', (t[max(0,i-140):i+240].replace(chr(10), ' ') if i >= 0 else ''))
open(r'<tmp>\sc2.html', 'w', encoding='utf-8').write(t)
print('saved')
