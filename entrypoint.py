#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import requests
import unidiff
from github import Github
from codespell_lib._codespell import (build_dict, default_dictionary,
                                      word_regex_def, fix_case)


def setup_dict():
    misspellings = {}
    build_dict(default_dictionary, misspellings, set())
    return misspellings


def get_patched_files(diff_text):
    patchset = unidiff.PatchSet(diff_text)
    patched_files = {}
    for patch in patchset:
        diff_file = patch.path
        for hunk in patch:
            for line in hunk.target_lines():
                if line.is_added:
                    patched_files.setdefault(diff_file, []).append((line.target_line_no,
                                                                    line.value))
    return patched_files


def check_spelling(pfiles, misspellings, word_regex):
    fixes = {}
    for fname in pfiles:
        for line_no, line_val in pfiles[fname]:
            for word in word_regex.findall(line_val):
                lword = word.lower()
                if lword in misspellings:
                    fixword = fix_case(word, misspellings[lword].data)
                    fixes.setdefault(fname, []).append((line_no, word, fixword))
    return fixes


def comment_pr(fixes, conf, token):
    if fixes:
        gh = Github(login_or_token=token)
        pr = gh.get_repo(conf['repository']['full_name']).get_pull(conf['number'])
        body = 'Possible misspellings:\n'
        for fname, fix in fixes.items():
            body += '- `{0!s}`\n'.format(fname)
            for line, wrong, right in fix:
                body += '  - line {0:d}: `{1!s}` => `{2!s}`\n'.format(line,
                                                                      wrong,
                                                                      right)
        pr.create_issue_comment(body=body)


def main():
    if len(sys.argv) < 2:
        print('No github token found, aborting!')
        return 1
    gh_token = sys.argv[1]
    if os.environ['GITHUB_EVENT_NAME'] != 'pull_request':
        print('We only work on pull requests. Doing nothing.')
        return 0
    with open(os.environ['GITHUB_EVENT_PATH'], 'r') as f:
        conf = json.loads(f.read())
    if not conf:
        print('No GITHUB_EVENT_PATH in environment. Check Your workflow.')
        return 1
    if conf['action'] not in ['opened', 'edited', 'synchronize']:
        print('Action mismatch: {0!s}. Doing nothing.'.format(conf['action']))
        return 0
    diff_url = conf['pull_request']['diff_url']
    diff_request = requests.request(method='GET', url=diff_url)
    if diff_request.status_code != 200:
        print('Could not get diff of pull request. Aborting.')
        return 1
    pfiles = get_patched_files(diff_request.text)
    word_regex = re.compile(word_regex_def)
    misspellings = setup_dict()
    fixes = check_spelling(pfiles, misspellings, word_regex)
    print("pfiles", pfiles)
    print("word_regex", word_regex)
    print("MISSPELS", misspellings)
    print("FIXES", fixes)
    print("CONF", conf)
    comment_pr(fixes, conf, gh_token)
    return 0


if __name__ == '__main__':
    main()
