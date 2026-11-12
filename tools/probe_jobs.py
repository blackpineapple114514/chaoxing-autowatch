# -*- coding: utf-8 -*-
"""从 Python 拉某个章节的任务点详情（视频 objectId/jobid/duration）。"""
import sys, re, json, time
sys.path.insert(0, r'<repo>\tools')
from cx import make_session

s = make_session()
clazzid, courseid, cpi, kid = '153630595', '226942553', '000000000', '586200478'
url = (f'https://mooc1.chaoxing.com/mooc-ans/knowledge/cards?clazzid={clazzid}&courseid={courseid}'
       f'&knowledgeid={kid}&num=0&ut=s&cpi={cpi}&v=2025-0424-1038-3&mooc2=1&isMicroCourse=false&editorPreview=0')
r = s.get(url, timeout=25, headers={'Referer': f'https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId={kid}&courseId={courseid}&clazzid={clazzid}&cpi={cpi}'})
t = r.text
print('status', r.status_code, 'len', len(t))
i = t.find('mArg = ')
seg = t[i:i+4000] if i >= 0 else ''
m = re.search(r'mArg = (\{.*?\});', t, re.S)
if m:
    raw = m.group(1)
    print('mArg len', len(raw))
    open(r'<tmp>\marg.json', 'w', encoding='utf-8').write(raw)
    d = json.loads(raw)
    atts = d.get('attachments', [])
    print('attachments', len(atts))
    for a in atts:
        print({k: a.get(k) for k in ['type', 'jobid', 'objectId', 'objectid', 'mid', 'attDurationEnc', 'headOffset', 'isPassed']})
    print('defaults keys:', list(d.get('defaults', {}).keys()))
    print('defaults subset:', {k: d['defaults'].get(k) for k in ['userid', 'clazzId', 'courseId', 'cpi', 'reportUrl', 'initdataUrl', 'ktoken', 'mtEnc', 'defenc']})
else:
    print('mArg not found; idx', i)
    print(t[:400])
