# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, r'<repo>\tools')
from cx import make_session

s = make_session()
courseid, clazzid, cpi, kid = '226942553', '153630595', '000000000', '586200478'
pages = {
 'studentstudy': f'https://mooc1.chaoxing.com/mycourse/studentstudy?chapterId={kid}&courseId={courseid}&clazzid={clazzid}&cpi={cpi}&enc=fe5966a5c14c8478375c1e3808dfdf77&mooc2=1&hidetype=0&fanyaVersion=0',
 'cards': f'https://mooc1.chaoxing.com/mooc-ans/knowledge/cards?clazzid={clazzid}&courseid={courseid}&knowledgeid={kid}&num=0&ut=s&cpi={cpi}&v=2025-0424-1038-3&mooc2=1&isMicroCourse=false&editorPreview=0',
 'sc-ans': f'https://mooc2-ans.chaoxing.com/mooc2-ans/mycourse/studentcourse?courseid={courseid}&clazzid={clazzid}&cpi={cpi}&ut=s',
}
for label, url in pages.items():
    t = s.get(url, timeout=25).text
    print(f'== {label} len={len(t)} dtoken@{t.find("dtoken")}')
    i = t.find('dtoken')
    if i >= 0:
        print('   ', t[max(0, i-260):i+260])
