#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# version 1.0.1

import argparse
import json
import re
from collections import defaultdict
import yaml
from jira import JIRA
try:
   import protobix3 as protobix
except:
   import protobix


JIRA_B_URL = ""
JIRA_B_USER = ""
JIRA_B_PASS = ""
MAX_RESULTS = 1000
ZABBIX_HOST = ""
PBX_SERVER = ""
PBX_PORT = 00000


def normalize_for_zabbix(string):
    res = re.sub(r'[^a-zA-Z0-9_]', '_', string)
    return res.lower()


def count_tasks_by_priority_types(all_issues, components, labels, exclude_issue):
    results = defaultdict(int)
    metrics_list = []

    # формируем список меток + приоритет
    for comp in components:
        for label in labels:
            name = '{0} {1}'.format(comp, label)
            key = normalize_for_zabbix('{0}_{1}'.format(comp, label))
            results[key] = {'value': 0,
                            'name': name}

    # список итемов для суммы по меткам, уже без деления на приоритеты
    for label in labels:
        name = 'Sum of {1}'.format(comp, label)
        key = normalize_for_zabbix('sum_{1}'.format(comp, label))
        results[key] = {'value': 0,
                        'name': name}

    for issue in all_issues:
        if re.search(issue.key, ' '.join(exclude_issue)):
            continue
        issue_components = {component.name for component in issue.fields.components}
        issue_labels = set(issue.fields.labels)
        # Проверяем каждый компонент и метку
        for comp in components:
            if comp in issue_components:
                for label in labels:
                    if label in issue_labels:
                        key = normalize_for_zabbix('{0}_{1}'.format(comp, label))
                        sum_label = normalize_for_zabbix('sum_{0}'.format(label))
                        results[key]['value'] += 1
                        results[sum_label]['value'] += 1
                break

    for key, value in results.items():
        metrics_list.append({'key': key,
                             'value': value['value'],
                             'name': value['name']})
    return metrics_list


def load_configuration(conf_name):
    with open(conf_name, "r") as file:
        conf = yaml.safe_load(file)
    return conf['PRIORITIES'], conf['ISSUE_TYPE']


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",
                        type=str,
                        help='Config name with all labels for count',
                        default="labels_list.yaml"
                        )
    return parser.parse_args()


def data_send(send_data, item_type):
    container = protobix.DataContainer()
    container.server_active = PBX_SERVER
    container.server_port = PBX_PORT
    container.data_type = item_type
    container.add(send_data)
    container.send()


def main():
    try:
        args = parse_args()
        conf_name = args.config
        issue_with_problem_tag, zabbix_data = [], {}
        jira_priorities_list, jira_issue_types = load_configuration(conf_name)

        # авторизация в оранжевой Jira
        o_jira = JIRA(basic_auth=(JIRA_B_USER, JIRA_B_PASS),
                      options={'server': JIRA_B_URL},
                      get_server_info=True)
        jql = 'project = PROJECT_NAME AND resolution = Unresolved ' \
              'AND status != Done and (labels not in (onduty) OR labels is EMPTY) and type != Epic'
        info = o_jira.search_issues(jql, maxResults=MAX_RESULTS)

        for issue in info:
            res = o_jira.issue(issue).raw
            all_labels = ', '.join(res['fields']['labels'])
            try:
                all_components = ', '.join([component.name for component in issue.fields.components])
            except:
                all_components = ''

            # если недостаточно меток или больше одной того же типа, добавим в исключения и не будем считать
            if (not re.search('.*From_.*Type_.*|.*Type_.*From_.*', all_labels) \
                    or all_labels.count('From_') > 1 \
                    or all_labels.count('Type_') > 1) \
                    and re.search('.*PRIORITY[0-9].*', all_components):
                issue_with_problem_tag.append('{0} - {1}'.format(issue, all_labels))
        res = count_tasks_by_priority_types(info, jira_priorities_list, jira_issue_types, issue_with_problem_tag)

        lld_list = []
        zabbix_data = {}
        for snd_metric in res:
            lld_list.append(snd_metric['key'])
            zabbix_data.update(
                {
                    "metric_[{}]".format(snd_metric['key']): "{}".format(snd_metric['value'])
                }
            )
        zabbix_data['project_metrics'] = "{}".format(
            json.dumps(
                {
                    'data': [{'{#METRIC}': snd_metric['key'],
                              '{#NAME_PR}': snd_metric['name'],
                              } for snd_metric in res]
                },
                indent=4
            )
        )

        zabbix_data.update({'tags_problem': '\n'.join(issue_with_problem_tag)})
        zabbix_data.update({'config_diff': '\n'.join(sorted(jira_issue_types))})
        zabbix_data.update({'exitcode': 1})

    except Exception as e:
        zabbix_data.update({'exitcode': 0})
        pass

    final_data = {ZABBIX_HOST: zabbix_data}
    data_send(final_data, "items")


if __name__ == "__main__":
    main()
