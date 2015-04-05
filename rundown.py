#!/usr/bin/env python2

from collections import namedtuple
import os
import re
import subprocess
import sys
import tempfile


GITHUB_BASE_URL = 'https://github.com/benoit-pierre/mcomix/'


Batch = namedtuple('Batch', 'subject changelist')


def get_commit_log(hash):
    subject, body = subprocess.check_output(
        ['git', 'log', '-1', '--format=%s%x00%b', hash]
    ).split('\0')
    body = body.strip()
    return subject, body


if 2 != len(sys.argv):
    sys.exit(1)

revspec = sys.argv[1]

log = tempfile.NamedTemporaryFile(prefix='rundown', delete=False)

try:
    if os.path.exists(revspec):
        changelist = open(revspec).readlines()
    else:
        subprocess.check_call(
            ['git', 'log', '--reverse', '--format=%h %s', revspec],
            stdout=log
        )
        log.close()
        subprocess.check_call(['vim', log.name, '+set ft=gitrebase'])
        changelist = open(log.name).readlines()

finally:
    os.unlink(log.name)

batch_list = []
batch = None

for line in changelist:

    if line.endswith('\n'):
        line = line[:-1]

    if '' == line:
        # End of batch if any.
        batch = None
        continue

    match = re.match(r'^([0-9a-f]{7,}) (.*)$', line)
    if match is None:
        # New batch.
        batch = Batch(line, [])
        batch_list.append(batch)
        continue

    # Change entry.
    hash, subject = match.groups()

    if batch is None:
        batch_list.append(Batch(subject, [hash]))
    else:
        batch.changelist.append(hash)

for batch in batch_list:
    github_url = GITHUB_BASE_URL
    if 1 == len(batch.changelist):
        github_url += 'commit/%s' % batch.changelist[0]
    else:
        # %5E: ^
        github_url += 'compare/%s%%5E...%s' % (batch.changelist[0], batch.changelist[-1])

    print '**[%s](%s)**' % (batch.subject, github_url)
    print

    if 1 == len(batch.changelist):
        subject, body = get_commit_log(batch.changelist[0])
        if body:
            print body
            print
    else:
        for hash in batch.changelist:
            subject, body = get_commit_log(hash)
            print '* %s' % subject
        print


