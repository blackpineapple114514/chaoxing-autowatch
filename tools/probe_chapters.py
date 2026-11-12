# -*- coding: utf-8 -*-
import sys, json, re, time
sys.path.insert(0, r'<repo>\tools')
from cx import make_session

s = make_session()
courseid, clazzid, cpi = '226942553', '153630595', '000000000'
url = f'https://mooc1.chaoxing.com/mycourse/studentcourse?courseId={courseid}&clazzid={clazzid}&cpi={cpi}&ut=s&t={int(time.time()*1000)}'
r = s.get(url, timeout=25, headers={'Referer': 'https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction'})
t = r.text
print('status', r.status_code, 'len', len(t))
for key in ['chapterId', 'knowledgeid', 'catalog', 'jobcount', 'chapter', 'mArg', 'objectId']:
    i = t.find(key)
    print(f'-- {key} @ {i}')
    if i >= 0:
        print('   ', t[max(0, i-160):i+260].replace('\n', ' '))
open(r'<tmp>\studentcourse.html', 'w', encoding='utf-8').write(t)
print('saved tmp/studentcourse.html')
