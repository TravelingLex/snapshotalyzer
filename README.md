# snapshotalyzer
Demo project to manage AWS EC2 instance snapshots


## About

This project is a demo, and uses boto3 to manage AWS EC2 instance snapshots.

## Configuring

shotty uses the configuration file created by the AWS cli. e.g.

'aws configure --profile <PROFILE>'

## Running

'pipenv run "python .\shotty\shotty.py <--profile=PROFILE>
<--region=REGION> <command> <subcommand> <--project=PROJECT>"'

*profile* is optional
*region* is optional
*command* is instances, volumes, or snapshots
*subcommand* - depends on command
*project* is optional