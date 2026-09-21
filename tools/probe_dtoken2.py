# -*- coding: utf-8 -*-
"""验证：dtoken 从 ananas/status 拿，报告 URL 用 reportUrl + '/' + dtoken。"""
import sys, json, time
sys.path.insert(0, r'<repo>\tools')
from cx import make_session

s = make_session()
obj = '2b4b6ddfa1f17f4e330d828ea1f3b94e'
u = f'https://mooc1.chaoxing.com/ananas/status/{obj}?k=&flag=normal&ro=0&_dc={int(time.time()*1000)}'
r = s.get(u, timeout=25, headers={'Referer': 'https://mooc1.chaoxing.com/mycourse/studentstudy'})
print('status', r.status_code)
j = r.json()
print('dtoken:', j.get('dtoken'))
print('duration:', j.get('duration'))
print('keys:', list(j.keys())[:25])
