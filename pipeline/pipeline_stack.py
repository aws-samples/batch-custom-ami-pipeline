from aws_cdk import (
                     aws_codebuild as _codebuild,
                     aws_codecommit as _codecommit,
                     aws_codepipeline as _codepipeline,
                     aws_codepipeline_actions as _codepipeline_actions,
                     aws_stepfunctions as _sfn,
                     aws_batch_alpha as _batch,
                     aws_ecs as ecs,
                     aws_iam as _iam,
                     App, Stack, CfnOutput)
import json

from constructs import Construct

class PipelineStack(Stack):

    def __init__(self, scope: Construct, id: str, *, 
                                            repo_name: str = None, 
                                            state_machine: str = None,
                                            approval_email: list = None,
                                            **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Create CodeCommit repository instance. 
        code = _codecommit.Repository.from_repository_name(self, "ImportedRepo",
                                                          repo_name)

        # Form the ARN using StateMachine name. 
        my_state_machine_arn = "arn:aws:states:" + self.region + ":" + self.account + ":stateMachine:" + state_machine

        # Creat StateMachine instance from state machine Arn. 
        my_statemachine = _sfn.StateMachine.from_state_machine_arn(self, "MyStateMachine", state_machine_arn = my_state_machine_arn)

        # Policy Document for Packer tool.
        with open("packer/policy_doc.json", "r") as policydoc:
            packer_policy = policydoc.read()

        # Convert policy into dictonary format.
        codebuild_packer_policy = json.loads(packer_policy)
        codebuild_policy_doc = _iam.PolicyDocument.from_json(
            codebuild_packer_policy)

        codebuild_managed_policy = _iam.ManagedPolicy(
            self, "CodeBuildManagedPolicy", document=codebuild_policy_doc)

        # IAM role for packer tool
        instance_role = _iam.Role(self, "PackerInstanceRole",
                                  assumed_by=_iam.ServicePrincipal(
                                      "ec2.amazonaws.com"),
                                  managed_policies=[_iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess")])

        # Create Instance Profile for Packer instance. 
        instance_profile = _iam.CfnInstanceProfile(self, "MyInstanceProfile", roles=[
                                                   instance_role.role_name], instance_profile_name=str("BatchInstanceProfile"+self.region))

        # CodeBuild Role with packer policy.
        codebuild_role = _iam.Role(self, "CodeBuildRole",
                                   assumed_by=_iam.ServicePrincipal(
                                       "codebuild.amazonaws.com"),
                                   managed_policies=[_iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeBuildAdminAccess"),
                                                     _iam.ManagedPolicy.from_managed_policy_arn(
                                       self, "MyCustomPolicy", managed_policy_arn=codebuild_managed_policy.managed_policy_arn)
                                   ])

        # CodePipeline Policy document.
        with open("packer/pipeline_policy.json", "r") as cd_policydoc:
            codepipeline_policy = cd_policydoc.read()
        
       # Convert policy into dictonary format.
        codepipeline_iam_policy = json.loads(codepipeline_policy)
        codepipeline_policy_doc = _iam.PolicyDocument.from_json(codepipeline_iam_policy)
        codepipeline_managed_policy = _iam.ManagedPolicy(
            self, "CodePipelineManagedPolicy", document=codepipeline_policy_doc)

        # CodePipeline Service IAM Role.
        codepipeline_role = _iam.Role(self, "CodePipelineRole",
                                   assumed_by=_iam.ServicePrincipal(
                                       "codepipeline.amazonaws.com"),
                                   managed_policies=[_iam.ManagedPolicy.from_aws_managed_policy_name("AWSStepFunctionsFullAccess"),
                                                     _iam.ManagedPolicy.from_aws_managed_policy_name("AWSCodeCommitFullAccess"), 
                                                     _iam.ManagedPolicy.from_managed_policy_arn(
                                       self, "MyCPPolicy", managed_policy_arn=codepipeline_managed_policy.managed_policy_arn)
                                   ]) 
        # Read CodeBuild buildspec.yaml file.
        with open("packer/buildspec.yml", "r") as file:
            build_spec = file.read()

        # CodeBuild Project to build custom AMI using packer tool.
        custom_ami_build = _codebuild.PipelineProject(self, "CustomAMIBuild",
                                                     role=codebuild_role,
                                                     build_spec=_codebuild.BuildSpec.from_source_filename(
                                                         build_spec),
                                                     environment_variables={"NAMETAG": _codebuild.BuildEnvironmentVariable(value="BatchAMI1"),
                                                                            "InstanceIAMRole": _codebuild.BuildEnvironmentVariable(value=instance_profile.instance_profile_name)},
                                                     environment=dict(build_image=_codebuild.LinuxBuildImage.from_code_build_image_id("aws/codebuild/standard:5.0")))

        # Code Build project to synth Test and Batch final environment cloudformation template. 
        batch_build = _codebuild.PipelineProject(self, "BatchBuild",
                                                build_spec=_codebuild.BuildSpec.from_object(dict(
                                                    version="0.2",
                                                    phases=dict(
                                                        install=dict(
                                                            commands=[
                                                                "npm install aws-cdk",
                                                                "npm update",
                                                                "python -m pip install -r requirements.txt"
                                                            ]),
                                                        build=dict(commands=[
                                                            "npx cdk synth -o dist"
                                                            ])),
                                                    artifacts={
                                                        "base-directory": "dist",
                                                        "files": [
                                                            "BatchStack.template.json",
                                                            "TestStack.template.json"]},
                                                    )),
                                                    environment=dict(build_image=_codebuild.LinuxBuildImage.from_code_build_image_id("aws/codebuild/amazonlinux2-x86_64-standard:4.0")))
        
     
        # Artificat instances. 
        source_output = _codepipeline.Artifact()
        batch_build_output = _codepipeline.Artifact("BatchBuildOutput")
        custom_ami_build_output = _codepipeline.Artifact("CustomAMIBuildOutput")
  
        # Test Job Def
        self.cfn_job_def = _batch.JobDefinition(self, "MyJobDef",
                                           job_definition_name="BatchCDKJobDef",
                                           container=_batch.JobDefinitionContainer(image=ecs.ContainerImage.from_registry(
                                               "public.ecr.aws/amazonlinux/amazonlinux:latest"), command=["sleep", "60"], memory_limit_mib=512, vcpus=1),
                                           )

        # Create CodePipeline. 
        self.amicode_pipeline = _codepipeline.Pipeline(self, "Pipeline",
            pipeline_name="MyPipeline",
            role=codepipeline_role,
            stages=[
                _codepipeline.StageProps(stage_name="Source",
                    actions=[
                        _codepipeline_actions.CodeCommitSourceAction(
                            action_name="CodeCommit_Source",
                            branch="main",
                            repository=code,
                            output=source_output)]),
                _codepipeline.StageProps(stage_name="Build",
                    actions=[
                        _codepipeline_actions.CodeBuildAction(
                            action_name="Batch_Build",
                            project=batch_build,
                            input=source_output,
                            run_order=2,
                            outputs=[batch_build_output]),
                        _codepipeline_actions.CodeBuildAction(
                            action_name="CustomAMI_Build",
                            variables_namespace="BuildVariables",
                            project=custom_ami_build,
                            run_order=1,
                            input=source_output,
                            outputs=[custom_ami_build_output])
                        ]),
                _codepipeline.StageProps(stage_name="Test",
                    actions=[
                        _codepipeline_actions.CloudFormationCreateUpdateStackAction(
                              action_name="Batch_CFN_Deploy",
                              template_path=batch_build_output.at_path(
                                  "TestStack.template.json"
                              ),
                              run_order=1,
                              stack_name="TestDeployStack",
                              parameter_overrides={"ImageId":"#{BuildVariables.AMIID}","TestEnv":"#{BuildVariables.TestEnv}"},
                              admin_permissions=True,
                              replace_on_failure=True,
                              extra_inputs=[custom_ami_build_output,batch_build_output]
                              ),
                        _codepipeline_actions.StepFunctionInvokeAction(
                            action_name="Invoke",
                            state_machine=my_statemachine,
                            role=codepipeline_role,
                            run_order=2
                            ),
                        _codepipeline_actions.CloudFormationDeleteStackAction(
                              action_name="Delete_TestEnv",
                              run_order=3,
                              stack_name="TestDeployStack",
                              admin_permissions=True
                            )
                            ]
                            ),
                _codepipeline.StageProps(stage_name="FinalStack",
                    actions=[
                        _codepipeline_actions.ManualApprovalAction(
                                action_name="ApproveChanges",
                                notify_emails=approval_email,
                                run_order=1),
                        _codepipeline_actions.CloudFormationCreateUpdateStackAction(
                              action_name="Batch_CFN_Deploy",
                              template_path=batch_build_output.at_path(
                                  "BatchStack.template.json"
                              ),
                              run_order=2,
                              stack_name="BatchDeployStack",
                              parameter_overrides={"ImageId":"#{BuildVariables.AMIID}","MainEnv":"#{BuildVariables.MainEnv}"},
                              admin_permissions=True,
                              extra_inputs=[custom_ami_build_output,batch_build_output]
                              )]
                            )  
                ]
            )

        url_output= ['https://console.aws.amazon.com/codepipeline/home?region=', self.region, '#/view/MyPipeline' ]
        CfnOutput(self, "PipelineOutput", value=("".join(url_output)))