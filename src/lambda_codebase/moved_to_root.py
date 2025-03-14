# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Executes as part of Step Functions when an AWS Account
is moved to the root of the Organization.
"""

import ast
import os
from thread import PropagatingThread
import boto3

from sts import STS
from parameter_store import ParameterStore
from partition import get_partition
from logger import configure_logger
from cloudformation import CloudFormation

LOGGER = configure_logger(__name__)
REGION_DEFAULT = os.environ.get('AWS_REGION')
S3_BUCKET = os.environ.get("S3_BUCKET_NAME")


def worker_thread(sts, region, account_id, role, event):
    partition = get_partition(REGION_DEFAULT)

    role = sts.assume_cross_account_role(
        f'arn:{partition}:iam::{account_id}:role/{role}',
        'remove_base'
    )

    parameter_store = ParameterStore(region, role)
    paginator = parameter_store.client.get_paginator('describe_parameters')
    page_iterator = paginator.paginate()
    for page in page_iterator:
        for parameter in page['Parameters']:
            is_adf_param = (
                'Used by The AWS Deployment Framework' in parameter.get(
                    'Description',
                    '',
                )
            )
            if is_adf_param:
                parameter_store.delete_parameter(parameter.get('Name'))

    cloudformation = CloudFormation(
        region=region,
        deployment_account_region=event.get('deployment_account_region'),
        role=role,
        wait=True,
        stack_name=None,
        s3=None,
        s3_key_path=None,
        account_id=account_id
    )
    return cloudformation.delete_all_base_stacks()


def remove_base(account_id, regions, role, event):
    sts = STS()
    threads = []

    for region in list(set([event.get('deployment_account_region')] + regions)):
        t = PropagatingThread(
            target=worker_thread,
            args=(
                sts,
                region,
                account_id,
                role,
                event,
            ),
        )
        t.start()
        threads.append(t)

    for thread in threads:
        thread.join()


def execute_move_action(action, account_id, parameter_store, event):
    LOGGER.info('Move to root action is %s for account %s', action, account_id)
    if action in ['remove_base', 'remove-base']:
        regions = (
            ast.literal_eval(
                parameter_store.fetch_parameter('target_regions')
            )
            or []
        )

        role = parameter_store.fetch_parameter('cross_account_access_role')
        return remove_base(account_id, regions, role, event)
    return True


def lambda_handler(event, _):
    parameter_store = ParameterStore(REGION_DEFAULT, boto3)
    configuration_options = ast.literal_eval(
        parameter_store.fetch_parameter('config')
    )

    to_root_option = list(filter(
        lambda option: option.get("name", []) == "to-root",
        configuration_options.get('moves')
    ))

    action = to_root_option.pop().get('action')
    account_id = event.get('account_id')
    execute_move_action(action, account_id, parameter_store, event)

    return event
