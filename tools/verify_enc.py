# -*- coding: utf-8 -*-
import hashlib
SALT = "d_yHJ!$pdA~5"

def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def enc(clazz, uid, jobid, objid, playing_ms, dur_ms, clip):
    return md5("[%s][%s][%s][%s][%d][%s][%d][%s]" % (clazz, uid, jobid, objid, playing_ms, SALT, dur_ms, clip))

clazz = "153630595"; uid = "123456789"; job = "1662169846944338"
obj = "2b4b6ddfa1f17f4e330d828ea1f3b94e"; dur = 589; clip = "0_589"

tests = [
    (44000, "5c759584a2cb851b2b51963de4a93c0f", "md5 hook captured (t=44s)"),
    (0,     "3ffc3ac2ee310d17dc37d8c4de177c95", "observed enc in first report (playingTime=0)"),
]
for pm, exp, label in tests:
    got = enc(clazz, uid, job, obj, pm, dur*1000, clip)
    print(("OK " if got == exp else "MISMATCH "), label, "->", got, "(expect", exp + ")")

# attDurationEnc guess: same shape but with attDuration ms as the "playing" slot
for pm in (dur*1000, dur, 0):
    print("attDur guess pm=%s ->" % pm, enc(clazz, uid, job, obj, int(pm), dur*1000, clip), " (observed attDurationEnc=94e9a6aa23d57341f7f40f16f2329733)")

print()
print("SAMPLE STRING:", "[%s][%s][%s][%s][%d][%s][%d][%s]" % (clazz, uid, job, obj, 44000, SALT, dur*1000, clip))
