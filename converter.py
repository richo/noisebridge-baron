#!/usr/bin/env python

"""
This converts the old flatfile format to the new json format
"""

import sys, json, hashlib

data = {}

for line in sys.stdin:
    if '#' in line:
        code, comment = line.strip().split('#', 1)
    else:
        code = line
        comment = ''
    code = code.strip()
    if code:
        hashedcode = hashlib.sha1( code ).hexdigest()
        nickname = "pseudonym %s" % hashlib.sha1( comment + code ).hexdigest()[:7]
        data[ hashedcode ] = dict( comment=comment, nickname=nickname )

print json.dumps( data, indent=2 )
