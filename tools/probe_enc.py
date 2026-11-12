# -*- coding: utf-8 -*-
import sys, re, hashlib, time
sys.path.insert(0, r'<repo>\tools')
from cx import make_session

TARGET = '000d181f40bb48a2908a6326641d79ce'
def md5(s): return hashlib.md5(s.encode()).hexdigest()

# 尝试 _from 组合
froms = ['226942553_153630595_123456789_fe5966a5c14c8478375c1e3808dfdf77',
         '226942553_153630595_123456789_',
         '_226942553_153630595_123456789_']
print('md5(_from):', [md5(x) for x in froms])

s = make_session()
courseid, clazzid, cpi, kid = '226942553', '153630595', '000000000', '586200478'

for label, url in [
    ('stucoursemiddle', f'https://mooc1.chaoxing.com/visit/stucoursemiddle?courseid={courseid}&clazzid={clazzid}&cpi={cpi}&ismooc2=1&v=2'),
    ('studentstudy', f'https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId={kid}&courseId={courseid}&clazzid={clazzid}&cpi={cpi}&enc=fe5966a5c14c8478375c1e3808dfdf77&mooc2=1&hidetype=0&fanyaVersion=0'),
    ('cards', f'https://mooc1.chaoxing.com/mooc-ans/knowledge/cards?clazzid={clazzid}&courseid={courseid}&knowledgeid={kid}&num=0&ut=s&cpi={cpi}&v=2025-0424-1038-3&mooc2=1&isMicroCourse=false&editorPreview=0'),
]:
    try:
        r = s.get(url, timeout=25, allow_redirects=True)
        t = r.text
        print(f'== {label} {r.status_code} len={len(t)} final={r.url[:90]}')
        for k in [TARGET, 'multimedia/log', 'reportUrl', '_from']:
            i = t.find(k)
            if i >= 0:
                print(f'   FOUND {k!r} @ {i}: ...{t[max(0,i-150):i+180]}...')
    except Exception as e:
        print(label, 'ERR', e)
