#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from jira import JIRA


JIRA_O_URL = ''
MAX_RESULTS = 1000


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True, type=str)
    parser.add_argument('--user', required=True, type=str)
    parser.add_argument('--password', required=True, type=str)
    parser.add_argument('--comment', required=True, type=str, help='Комментарий для закрытия задачи')
    return parser.parse_args()


def main():
    try:
        args = parse_args()
        query_o_jira = args.query

        jira = JIRA(
            basic_auth=(args.user, args.password),
            options={
                'server': JIRA_O_URL
            },
            get_server_info=True)
        try:
            orange_tasks = jira.search_issues(query_o_jira, maxResults=MAX_RESULTS)
        except Exception as e:
            print('JQL Error, {}'.format(e))
            exit(1)

        for orange_task in orange_tasks:
            jra = jira.issue(orange_task)

            # вывести доступные переходы задач
            res = jira.transitions(jra)
            enabled_transitions = [(t['id'], t['name']) for t in res]
            for transition in enabled_transitions:
                if '91' in transition:
                    jira.transition_issue(
                        jra,
                        transition='91',
                        comment=str(args.comment),
                        fields={
                            'resolution': {'id': '1'},
                            'assignee': {'name': args.user}
                            },
                        worklog='1'
                        )

    except Exception as e:
        print(e)


if __name__ == '__main__':
    main()
