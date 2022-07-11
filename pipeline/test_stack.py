from tokenize import group
from aws_cdk import (
    aws_stepfunctions as _sfn,
    aws_batch_alpha as _batch,
    aws_stepfunctions_tasks as _sfn_tasks,
    aws_sns as _sns,
    aws_ec2 as _ec2,
    aws_ecs as _ecs,
    App, Stack, CfnParameter, Fn
)

from constructs import Construct

class TestStack(Stack):
    def __init__(self, app: App, id: str, vpc, state_machine: str = None, **kwargs):
        super().__init__(app, id, **kwargs)

        # Parameters
        ImageId = CfnParameter(self, "ImageId", type="String",
                                    description="This is Custom AMI ID", default='ami-013fdfa75ffcb9c9e')
        TestEnv = CfnParameter(self, "TestEnv", type="String",
                                    description="Batch Compute Environment name",default='Test-8-v2022-03-09')
                                    
        # Reading user data, to install custom packages into the ec2 instance.
        with open("packer/user_data.txt", "r") as myfile:
            userdata = myfile.read()

        # This create Launch template data using AMI ID and userdata script.
        my_launch_data = _ec2.CfnLaunchTemplate.LaunchTemplateDataProperty(
            image_id=ImageId.value_as_string,
            instance_type="c5n.18xlarge",
            user_data = Fn.base64(userdata))
        my_launch_template = _ec2.CfnLaunchTemplate(self, "BatchLaunchTemplate", launch_template_name="BatchEFA-LT",
                                                   launch_template_data=my_launch_data)

        ##### AWS BATCH COMPUTE ENVIRONMENT , BATCH JOB QUEUE AND BATCH JOB DEFINITION SECTION #####
        my_compute_environment = _batch.ComputeEnvironment(self, "AWS-Managed-Compute-Env",
                                                           compute_resources={
                                                               "launch_template": {"launch_template_name": my_launch_template.launch_template_name, "version": "$Latest"},
                                                               "vpc": vpc,
                                                               "type":_batch.ComputeResourceType.SPOT
                                                           },
                                                           compute_environment_name=TestEnv.value_as_string
                                                           )

        # Create AWS Batch JobQueue and associate it with Test Compute Environment. 
        test_queue = _batch.JobQueue(self, "JobQueue",
                                     compute_environments=[
                                         _batch.JobQueueComputeEnvironment(
                                             compute_environment=my_compute_environment,
                                             order=1
                                         )
                                     ]
                                     )

        self.cfn_job_def = _batch.JobDefinition(self, "TestJobDef",
                                           job_definition_name="TestBatchCDKJobDef",
                                           container=_batch.JobDefinitionContainer(image=_ecs.ContainerImage.from_registry(
                                               "public.ecr.aws/amazonlinux/amazonlinux:latest"), command=["sleep", "60"], memory_limit_mib=512, vcpus=1),
                                           )

        # Create Stepfunction submit job task.
        self.task_job = _sfn_tasks.BatchSubmitJob(self, "Submit Job",
                                                  job_definition_arn=self.cfn_job_def.job_definition_arn,
                                                  job_name="MyJob",
                                                  job_queue_arn=test_queue.job_queue_arn
                                                  )
        ##### END OF BATCH COMPUTE ENVIRONMENT SECTION #####

        topic = _sns.Topic(self, "Topic")
        
        self.task1 = _sfn_tasks.SnsPublish(self, "Publish_suceeded",
                                           topic=topic,
                                           message=_sfn.TaskInput.from_json_path_at(
                                               "$.StatusReason")
                                           )
        self.task2 = _sfn_tasks.SnsPublish(self, "Publish_failed",
                                           topic=topic,
                                           message=_sfn.TaskInput.from_json_path_at(
                                               "$.StatusReason")
                                           )
        definition = self.task_job.next(_sfn.Choice(self, "Job Complete?").when(_sfn.Condition.string_equals("$.Status", "FAILED"), self.task2).when(_sfn.Condition.string_equals("$.Status", "SUCCEEDED"), self.task1))
        self.statemachine = _sfn.StateMachine(
            self, "StateMachine",
            state_machine_name=state_machine,
            definition=definition,
        )