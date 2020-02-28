"""
Custom rules for cfn-lint
"""


import copy
import logging
import re
from cfnlint.rules import CloudFormationLintRule, RuleMatch # pylint: disable=import-error


LOGGER = logging.getLogger(__name__)


class MandatoryParametersRule(CloudFormationLintRule):
    """
    Check for Mandatory CloudFormation Parameters
    """

    id = "E9000"
    shortdesc = "Mandatory Parameters"
    description = "Ensuring that mandatory parameters are present"
    tags = ["ecommerce", "parameters"]

    _mandatory_parameters = ["Environment"]
    _message = "Missing parameter '{}'"

    def match(self, cfn):
        """
        Match missing mandatory parameters
        """

        mandatory_parameters = copy.deepcopy(self._mandatory_parameters)

        for key in cfn.get_parameters().keys():
            if key in mandatory_parameters:
                mandatory_parameters.remove(key)

        return [
            RuleMatch(["Parameters"], self._message.format(param))
            for param in mandatory_parameters
        ]


class Python38Rule(CloudFormationLintRule):
    """
    Check for Python3.8 usage
    """

    id = "E9001"
    shortdesc = "Python3.8 Lambda usage"
    description = "Ensure that Python3.8 is used by all Lambda functions"
    tags = ["ecommerce", "lambda"]

    _runtime = "python3.8"
    _message = "Function is using {} runtime instead of {}"

    def match(self, cfn):
        """
        Match against Lambda functions not using python3.8
        """

        matches = []

        for key, value in cfn.get_resources(["AWS::Lambda::Function"]).items():
            if value.get("Properties").get("Runtime") != self._runtime:
                matches.append(RuleMatch(
                    ["Resources", key],
                    self._message.format(value.get("Properties").get("Runtime"), self._runtime)
                ))

        return matches


class LambdaLogGroupRule(CloudFormationLintRule):
    """
    Check that all Lambda functions have a Log Group
    """

    id = "E9002"
    shortdesc = "Lambda Log group"
    description = "Ensure that all Lambda functions have a corresponding Log Group"

    tags = ["ecommerce", "lambda"]

    _message = "Function {} does not have a corresponding log group"

    def match(self, cfn):
        """
        Match functions that don't have a log group
        """

        matches = []

        functions = cfn.get_resources("AWS::Lambda::Function")
        log_groups = cfn.get_resources("AWS::Logs::LogGroup")

        known = []

        # Scan log groups for resource names
        for resource in log_groups.values():
            # This use an autogenerated log group name
            if "LogGroupName" not in resource.get("Properties"):
                continue

            log_group_name = resource.get("Properties").get("LogGroupName")
            # This doesn't have a !Sub transformation
            if not isinstance(log_group_name, dict) or "Fn::Sub" not in log_group_name:
                continue

            match = re.search(r"\${(?P<func>[^}]+)}", log_group_name["Fn::Sub"])
            if match is not None:
                known.append(match["func"])

        # Scan functions against log groups
        for function in functions.keys():
            if function not in known:
                matches.append(RuleMatch(
                    ["Resources", function],
                    self._message.format(function)
                ))

        return matches


class LambdaESMDestinationConfig(CloudFormationLintRule):
    """
    Check that Lambda Event Source Mapping have a DestinationConfig with OnFailure destination
    """

    id = "E9003"
    shortdesc = "Lambda EventSourceMapping OnFailure"
    description = "Ensure that Lambda Event Source Mapping have a DestinationConfig with OnFailure destination"

    _message = "Event Source Mapping {} does not have a DestinationConfig with OnFailure destination"

    def match(self, cfn):
        """
        Match EventSourceMapping that don't have a DestinationConfig with OnFailure
        """

        matches = []

        sources = cfn.get_resources("AWS::Lambda::EventSourceMapping")

        # Scan through Event Source Mappings
        for key, resource in sources.items():
            if resource.get("Properties", {}).get("DestinationConfig", {}).get("OnFailure", None) is None:
                matches.append(RuleMatch(
                    ["Resources", key],
                    self._message.format(key)
                ))

        return matches

class LambdaRuleInvokeConfig(CloudFormationLintRule):
    """
    Check that Lambda functions invoked by EventBridge have a corresponding EventInvokeConfig
    """

    id = "E9004"
    shortdesc = "Lambda EventBridge OnFailure"
    description = "Ensure that Lambda functions invoked by EventBring have an Event Invoke Config with OnFailure destination"

    _message = "Rule {} does not have a corresponding Event Invoke Config with OnFailure destination"

    def match(self, cfn):
        """
        Match Events Rules that don't have a corresponding EventInvokeConfig
        """

        matches = []

        function_names = cfn.get_resources("AWS::Lambda::Function").keys()
        rules = cfn.get_resources("AWS::Events::Rule")
        invoke_configs = cfn.get_resources("AWS::Lambda::EventInvokeConfig")

        # Get the list of function names with EventInvokeConfig and OnFailure
        invoke_config_functions = []
        for resource in invoke_configs.values():
            if resource.get("Properties", {}).get("DestinationConfig", {}).get("OnFailure", None) is None:
                continue
            invoke_config_functions.append(resource["Properties"]["FunctionName"]["Ref"])

        # Parse rules
        for key, resource in rules.items():
            for target in resource.get("Properties", {}).get("Targets", []):
                if target.get("Arn", {}).get("Fn::GetAtt", None) is None:
                    continue

                if target["Arn"]["Fn::GetAtt"][0] not in function_names:
                    continue

                function_name = target["Arn"]["Fn::GetAtt"][0]
                if function_name not in invoke_config_functions:
                    matches.append(RuleMatch(
                        ["Resources", key],
                        self._message.format(key)
                    ))

        return matches
