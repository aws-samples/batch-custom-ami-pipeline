from aws_cdk import (
                    aws_batch_alpha as _batch,
                    aws_ec2 as _ec2,
                    App, Stack, CfnParameter, Fn )

from constructs import Construct

class BatchStack(Stack):
    def __init__(self, app: App, id: str, vpc, **kwargs):
        super().__init__(app, id, **kwargs)
        # Parameters
        ImageId = CfnParameter(self, "ImageId", type="String",
                                    description="This is Custom AMI ID")
        MainEnv = CfnParameter(self, "MainEnv", type="String",
                                    description="Batch Compute Environment name")

        # Read userdata script in a file.
        with open("packer/user_data.txt", "r") as myfile:
            userdata = myfile.read()

        # Create launch template data using image id and userdata script.
        my_launch_data = _ec2.CfnLaunchTemplate.LaunchTemplateDataProperty(
            image_id=ImageId.value_as_string,
            instance_type="c5n.18xlarge",
            user_data = Fn.base64(userdata))

        my_launch_template = _ec2.CfnLaunchTemplate(self, "BatchLaunchTemplate",
                                                    launch_template_name="batch-main-template",
                                                    launch_template_data=my_launch_data)
        # default is managed
        my_compute_environment = _batch.ComputeEnvironment(self, "AWS-Managed-Compute-Env",
                                                           compute_resources={
                                                               "launch_template": {"launch_template_name": my_launch_template.launch_template_name, "version": "$Latest"},
                                                            #    "placement_group": "MyCfnPlacementGroup",
                                                               "vpc": vpc
                                                           },
                                                           compute_environment_name=MainEnv.value_as_string
                                                           )
        # Example automatically generated without compilation. See https://github.com/aws/jsii/issues/826
        self.batch_queue = _batch.JobQueue(self, "JobQueue",
                                           compute_environments=[
                                               _batch.JobQueueComputeEnvironment(
                                                   compute_environment=my_compute_environment,
                                                   order=1
                                               )
                                           ])
