# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Module used for working with Targets within the Deployment Map.
Targets are the stages/steps within a Pipeline and can
require mutation depending on their structure.
"""

import re
import os
from errors import InvalidDeploymentMapError, NoAccountsFoundError
from logger import configure_logger
from schema_validation import AWS_ACCOUNT_ID_REGEX_STR


LOGGER = configure_logger(__name__)
ADF_DEPLOYMENT_ACCOUNT_ID = os.environ["ACCOUNT_ID"]
AWS_ACCOUNT_ID_REGEX = re.compile(AWS_ACCOUNT_ID_REGEX_STR)


class TargetStructure:
    def __init__(self, target):
        self.target = TargetStructure._define_target_type(target)
        self.account_list = []
        self.wave = (
            target.get('wave', {})
            if isinstance(target, dict)
            else {}
        )
        self.exclude = (
            target.get('exclude', [])
            if isinstance(target, dict)
            else []
        )

    @staticmethod
    def _define_target_type(target):
        if isinstance(target, list):
            output = []
            for target_path in target:
                output.append({"path": [target_path]})
            target = output
        if isinstance(target, (int, str)):
            target = [{"path": [target]}]
        if isinstance(target, dict):
            if target.get('target'):
                target["path"] = target.get('target')
            if not target.get('path') and not target.get('tags'):
                target["path"] = '/deployment'
                LOGGER.debug(
                    'No path/target detected, defaulting to /deployment',
                )
            if not isinstance(target.get('path', []), list):
                target["path"] = [target.get('path')]
        if not isinstance(target, list):
            target = [target]
        return target

    def generate_waves(self):
        wave_size = self.wave.get('size', 50)
        waves = []
        length = len(self.account_list)
        for start_index in range(0, length, wave_size):
            end_index = min(
                start_index + wave_size,
                length,
            )
            waves.append(
                self.account_list[start_index:end_index],
            )
        return waves


class Target:
    """
    Target deployment configuration.
    """
    def __init__(
        self,
        path,
        target_structure,
        organizations,
        step,
    ):
        self.path = path
        self.step_name = step.get('name', '')
        self.provider = step.get('provider', 'cloudformation')
        self.properties = step.get('properties', {})
        self.regions = (
            [step.get('regions')]
            if not isinstance(step.get('regions'), list)
            else step.get('regions')
        )
        self.target_structure = target_structure
        self.organizations = organizations

    @staticmethod
    def _account_is_active(account):
        return bool(account.get('Status') == 'ACTIVE')

    def _create_target_info(self, name, account_id):
        return {
            "id": account_id,
            "name": re.sub(r'[^A-Za-z0-9.@\-_]+', '', name),
            "path": self.path,
            "properties": self.properties,
            "provider": self.provider,
            "regions": self.regions,
            "step_name": re.sub(r'[^A-Za-z0-9.@\-_]+', '', self.step_name)
        }

    def _target_is_approval(self):
        self.target_structure.account_list.append(
            self._create_target_info(
                'approval',
                'approval'
            )
        )

    def _create_response_object(self, responses):
        accounts_found = 0
        for response in responses:
            is_active_not_excluded = (
                Target._account_is_active(response)
                and not response.get('Id') in self.target_structure.exclude
            )
            if is_active_not_excluded:
                accounts_found += 1
                self.target_structure.account_list.append(
                    self._create_target_info(
                        response.get('Name'),
                        str(response.get('Id'))
                    )
                )
        if accounts_found == 0:
            raise NoAccountsFoundError(f"No accounts found in {self.path}")

    def _target_is_account_id(self):
        responses = self.organizations.client.describe_account(
            AccountId=str(self.path)
        ).get('Account')
        self._create_response_object([responses])

    def _target_is_tags(self):
        responses = self.organizations.get_account_ids_for_tags(self.path)
        accounts = []
        for response in responses:
            if response.startswith('ou-'):
                accounts.extend(
                    self.organizations.get_accounts_for_parent(response),
                )
            else:
                accounts.append(
                    self.organizations.client
                    .describe_account(AccountId=response)
                    .get('Account'),
                )
        self._create_response_object(accounts)

    def _target_is_ou_id(self):
        responses = self.organizations.get_accounts_for_parent(
            str(self.path)
        )
        self._create_response_object(responses)

    def _target_is_ou_path(self):
        responses = self.organizations.dir_to_ou(self.path)
        self._create_response_object(responses)

    def _target_is_null_path(self):
        # TODO we need to fetch this default path from parameter store
        self.path = '/deployment'
        responses = self.organizations.dir_to_ou(self.path)
        self._create_response_object(responses)

    def fetch_accounts_for_target(self):
        if self.path == 'approval':
            return self._target_is_approval()
        if isinstance(self.path, dict):
            return self._target_is_tags()
        if str(self.path).startswith('ou-'):
            return self._target_is_ou_id()
        if AWS_ACCOUNT_ID_REGEX.match(str(self.path)):
            return self._target_is_account_id()
        if str(self.path).isnumeric():
            LOGGER.warning(
                "The specified path is numeric, but is not 12 chars long. "
                "This typically happens when you specify the account id as a "
                "number, while the account id starts with a zero. If this is "
                "the case, please wrap the account id in quotes to make it a "
                "string. The current path is interpreted as '%s'. "
                "It could be interpreted as an octal number due to the zero, "
                "so it might not match the account id as specified in the "
                "deployment map. Interpreted as an octal it would be '%s'. "
                "This error is thrown to be on the safe side such that it "
                "is not targeting the wrong account by accident.",
                str(self.path),
                # Optimistically convert the path from 10-base to octal 8-base
                # Then remove the use of the 'o' char, as it will output
                # in the correct way, starting with: 0o.
                str(oct(int(self.path))).replace('o', ''),
            )
        if str(self.path).startswith('/'):
            return self._target_is_ou_path()
        if self.path is None:
            # No path/target has been passed, path will default to /deployment
            return self._target_is_null_path()
        raise InvalidDeploymentMapError(
            f"Unknown definition for target: {self.path}"
        )
