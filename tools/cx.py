# -*- coding: utf-8 -*-
"""共用 cookie 会话（测试用）。

cookie 从本机 `%USERPROFILE%\\.chaoxing-cookies.json` 或环境变量 `CX_COOKIES` 读取，
不写死在仓库里（见 `app/selftest.py` 同款约定）。
"""
import json, os
import requests, re

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'


def load_cookies():
    raw = os.environ.get('CX_COOKIES')
    if raw:
        d = json.loads(raw)
    else:
        p = os.path.join(os.path.expanduser('~'), '.chaoxing-cookies.json')
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
    return d.get('base') or {}, d.get('routes') or {}


def make_session():
    base, routes = load_cookies()
    s = requests.Session()
    s.headers.update({'User-Agent': UA})
    for k, v in base.items():
        s.cookies.set(k, v, domain='.chaoxing.com')
    for dom, v in routes.items():
        s.cookies.set('route', v, domain=dom)
    return s


def get_courses(s):
    body = 'courseType=1&courseFolderId=0&query=&pageHeader=-1&single=1&superstarClass=0&isFirefly=0&fid=&from='
    r = s.post('https://mooc2-ans.chaoxing.com/mooc2-ans/visit/courselistdata', data=body,
               headers={'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                        'X-Requested-With': 'XMLHttpRequest',
                        'Referer': 'https://mooc2-ans.chaoxing.com/mooc2-ans/visit/interaction'}, timeout=25)
    out = []
    for m in re.finditer(r'<div class="course clearfix[^"]*"[^>]*info="([^"]*)_([^"]*)"[^>]*id="c_(\d+)"', r.text):
        out.append({'clazzid': m.group(1), 'cpi': m.group(2), 'courseid': m.group(3)})
    names = re.findall(r'<span class="course-name overHidden2"[^>]*>\s*([^<]+)', r.text)
    for i, n in enumerate(names):
        if i < len(out):
            out[i]['name'] = n.strip()
    return out, r.text


if __name__ == '__main__':
    s = make_session()
    cs, html = get_courses(s)
    print('courses:', len(cs))
    for c in cs:
        print(c)
