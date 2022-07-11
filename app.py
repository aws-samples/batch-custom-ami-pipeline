#!/usr/bin/env python3

from aws_cdk import (App, Stack, CfnOutput, Tags)
from pipeline.pipeline_stack import PipelineStack
from pipeline.test_stack import TestStack
from pipeline.batch_stack import BatchStack
from pipeline.vpc_stack import VpcStack

from constructs import Construct

CODECOMMIT_REPO_NAME = "PIPELINE"
STATE_MACHINE = "MYSTATEMACHINE"
APPROVAL_EMAIL = ['abc@amazon.com']

app = App()

vpc_stack = VpcStack(app, "VpcStack")
pipeline_stack = PipelineStack(app, "PipelineCustomAMIStack", repo_name=CODECOMMIT_REPO_NAME, state_machine=STATE_MACHINE, approval_email=APPROVAL_EMAIL)
test_stack = TestStack(app, "TestStack", vpc=vpc_stack.vpc, state_machine=STATE_MACHINE)
batch_stack = BatchStack(app, "BatchStack", vpc=vpc_stack.vpc)

#Add Tags to all resources created using this project
Tags.of(vpc_stack).add("Project","Batch Custom AMI Resource")
Tags.of(pipeline_stack).add("Project","Batch Custom AMI Resource")
Tags.of(test_stack).add("Project","Batch Custom AMI Resource")
Tags.of(batch_stack).add("Project","Batch Custom AMI Resource")

app.synth()
