# Installation Guide

## Pre-Requisites

- [awscli](https://aws.amazon.com/cli/).
- [git](https://git-scm.com/)
  - [AWS CodeCommit Setup](https://docs.aws.amazon.com/codecommit/latest/userguide/setting-up-https-unixes.html)
- [AWS CloudTrail configured](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/cloudtrail-create-and-update-a-trail.html)
in the `us-east-1` region within the AWS Organizations Management AWS Account.

## Installation Instructions

1. Ensure you have setup [AWS CloudTrail](https://aws.amazon.com/cloudtrail/)
   *(Not the default trail)* in your Management Account that spans **all
   regions**, the trail itself can be created in any region. Events [triggered
   via
   CloudTrail](https://docs.aws.amazon.com/organizations/latest/userguide/orgs_incident-response.html)
   for AWS Organizations can only be acted upon in the US East (N. Virginia)
   Region.

2. In the AWS Console from your management account within `us-east-1`, head over
   to the Serverless Application Repository *(SAR)*. From there, search for
   `aws-deployment-framework` *(or "adf")* (ensure the checkbox *"Show apps that
   create custom IAM roles or resource policies"* is checked).

   If you are deploying ADF for the first time, fill in the required parameters
   for your specific use-case. For example, if you have no AWS Organization
   or dedicated deployment account already created, you can enter an account
   name and email address and ADF will create you an AWS Organization, the
   deployment OU, along with an AWS Account that will be used to house
   deployment pipelines throughout your Organization.

   If you already have an AWS Account you want to use as your deployment account
   you can specify its Account ID in the parameter `DeploymentAccountId`
   and leave the`DeploymentAccountName` and `DeploymentAccountEmail` empty.

   Next, specify the `DeploymentAccountMainRegion` parameter as the region that
   will host your deployment pipelines and would be considered your main AWS
   region.

   In the `DeploymentAccountTargetRegions` section of the parameters
   enter a list of AWS Regions that you might want to deploy your resources
   or applications into via AWS CodePipeline *(this can be updated whenever)*.
   Also specify a main notification endpoint *(email)* to receive updates
   about the bootstrap process.

   When you have entered all required information press **'Deploy'**.

3. As the stack `serverlessrepo-aws-deployment-framework` completes you can now
   open AWS CodePipeline from within the management account in `us-east-1` and
   see that there is an initial pipeline execution that has been started.

   When ADF is deployed for the first time, it will make the initial commit with
   the skeleton structure of the `aws-deployment-framework-bootstrap` CodeCommit
   repository.

   From that initial commit, you can clone the repository to your local
   environment and make the changes required to define your desired base stacks
   via AWS CloudFormation Templates, Service Control Policies or Tagging
   Policies.

4. As part of the AWS CodePipeline Execution from the previous step, the account
   provisioner component will run *(in CodeBuild)*.

   If you let ADF create a new Deployment account for you *(by not giving a
   pre-existing account id when deploying from SAR)*, then ADF will handle
   creating and moving this account automatically into the deployment OU.

   If you are using a pre-existing deployment account, you will need to move the
   account into the deployment OU from within the Organization console, or
   add your deployment account into a `.yml` file within the `adf-accounts`
   folder *(see docs)*. This action will trigger [AWS Step
   Functions](https://aws.amazon.com/step-functions/) to run and start the
   bootstrap process for the deployment account. You can view the progress of
   this in the AWS Step Functions console from the management account in the
   `us-east-1` region.

5. Once the Step Function has completed, switch roles over to the newly
   bootstrapped deployment account in the region you defined as your main region
   from step 2.

   An AWS CodeCommit repository will have been created and will contain the
   initial skeleton structure committed which serves as a starting point for
   defining your pipelines throughout your organization.

   Before defining pipelines, you will most likely want to create more AWS
   accounts and build out your Organization. Bootstrap further accounts by
   moving them into the OU that corresponds to their purpose.

   At this point you can follow the [sample guide](./samples-guide.md) to get
   started with the samples included in this repository which will show in
   detail how pipelines function in ADF.

   **Note** Each account you reference in your `deployment_map.yml` must be
   bootstrapped into an OU prior to adding it to a pipeline.
