# -*- coding: utf-8 -*-
"""用一份已有 cookie 测试纯 HTTP 读取课程列表。cookie 见 `tools/cx.py` 的 load_cookies()。"""
import requests

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'

from cx import load_cookies

BASE, ROUTES = load_cookies()

S = requests.Session()
S.headers.update({'User-Agent': UA})
for k, v in BASE.items():
    S.cookies.set(k, v, domain='.chaoxing.com')
for dom, v in ROUTES.items():
    S.cookies.set('route', v, domain=dom)

def probe(url, **kw):
    try:
        return S.request(url=url, timeout=25, allow_redirects=False, **kw)
    except Exception as e:
        print('ERR', url, e)
        return None

# 1) 课程列表
body = 'courseType=1&courseFolderId=0&query=&pageHeader=-1&single=1&superstarClass=0&isFirefly=0&fid=&from='
r = probe('https://mooc2-ans.chaoxing.com/mooc2-ans/visit/courselistdata', method='POST',
          data=body, headers={'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                              'X-Requested-With': 'XMLHttpRequest',
                              'Referer': 'https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction'})
if r is not None:
    t = r.text
    loc = r.headers.get('Location', '')
    print('courselistdata status', r.status_code, 'len', len(t), 'hasCourseid', 'courseid' in t, 'loc', loc)
    if 'courseid' in t:
        i = t.index('courseid')
        print('SAMPLE:', t[max(0, i-220):i+320])
    else:
        print('HEAD:', t[:250])

# 2) 我的课程页
r = probe('https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction', method='GET')
if r is not None:
    print('interaction status', r.status_code, 'len', len(r.text), 'loc', r.headers.get('Location', ''))
