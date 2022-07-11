from aws_cdk import ( 
                     aws_ec2 as _ec2, 
                     App, Stack
                     )

from constructs import Construct

class VpcStack(Stack):

    def __init__(self, app: App, id: str, **kwargs):
        super().__init__(app, id, **kwargs)

        # This resource alone will create a private/public subnet in each AZ as well as nat/internet gateway(s)
        vpc = _ec2.Vpc(self, "VPC")
        self.vpc = vpc
        