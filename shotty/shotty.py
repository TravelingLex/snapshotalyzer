import boto3
import botocore
import click
import datetime

def start_session(profile = 'shotty',region='us-east-2'):
    session = boto3.Session(profile_name = profile, region_name= region)
    ec2 = session.resource('ec2')
    return ec2

def filter_instances(ec2, project, server_id = None):
    instances = []

    if server_id:
        instances = ec2.instances.filter(InstanceIds=[server_id])
    elif project:
        filters = [{"Name":"tag:Project" , "Values":[project]}]
        instances = ec2.instances.filter(Filters=filters)
    else:
        instances = ec2.instances.all()
    return instances

def has_pending_snapshot(volume):
    snapshots = list(volume.snapshots.all())
    return snapshots and snapshots[0].state == 'pending'

def abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()


@click.group()
@click.option('--profile', default='shotty',
    help = 'Please specify an AWS profile.')
@click.option('--region', default='us-east-1',
    help = 'Please specify an AWS region.')
@click.pass_context
def cli(ctx,profile,region):
    """Establish Session Parameters"""
    ctx.ensure_object(dict)
    ctx.obj['PROFILE'] = profile
    ctx.obj['REGION'] = region

@cli.group('snapshots')
def snapshots():
    """Commands for snapshots"""

@snapshots.command('list')
@click.option('--project', default=None,
    help= "Only snapshots for project (tag Project:<name>)")
@click.option('--all', 'list_all', default=False, is_flag=True,
    help="List all snapshots for each volume, not just the most recent")
@click.option('--id', 'server_id', default=None,
    help="Specific instances")   
@click.pass_context
def list_snapshots(ctx,project, list_all,server_id):
    "List EC2 snapshots"

    ec2 = start_session(ctx.obj['PROFILE'],ctx.obj['REGION'])
    instances = filter_instances(ec2,project,server_id)

    for i in instances:
        for v in i.volumes.all():
            for s in v.snapshots.all():
                print(", ".join((
                    s.id,
                    v.id,
                    i.id,
                    s.state,
                    s.progress,
                    s.start_time.strftime("%c")
                )))
            
                if s.state == 'completed' and not list_all: break

    return 

@cli.group('volumes')
def volumes():
    """Commands for volumes"""

@volumes.command('list')
@click.option('--project', default=None,
    help= "Only volumes for project (tag Project:<name>)")
@click.pass_context
def list_volumes(ctx, project):
    "List EC2 volumes"

    ec2 = start_session(ctx.obj['PROFILE'],ctx.obj['REGION'])
    instances = filter_instances(ec2, project)
    
    for i in instances:
        for v in i.volumes.all():
            print(", ".join((
                v.id,
                i.id,
                v.state,
                str(v.size) + "GiB",
                v.encrypted and "Encrypted" or "Not Encrypted"
        
            )))
    return

@cli.group('instances')
def instances():
    """Commands for instances"""

@instances.command('snapshots',
    help= "Create Snapshot of all volumes")
@click.option('--project', default=None,
    help="Only instances for project (tag Project:<name>)")
@click.option('--force', flag_value=True, default=False,
    help='Force instances to stop')
@click.option('--yes', is_flag=True, callback=abort_if_false,
    expose_value=False,
    prompt='Are you sure you want to snapshot?')
@click.option('--id', 'server_id', default=None,
    help="Specific instances")
@click.option('--age', type=int, default=None,
    help="In days, if snapshot is newer than age, no snapshot will be made.")
@click.pass_context
def create_snapshots(ctx, project, force, server_id, age):
    "Create Snapshots for EC2 Instances"

    ec2 = start_session(ctx.obj['PROFILE'],ctx.obj['REGION'])
    instances = filter_instances(ec2, project, server_id)

    if force or project or server_id:
        try:
            today = datetime.datetime.utcnow()
            now = today.strptime(str(today)[:-7], "%Y-%m-%d %H:%M:%S")
            for i in instances:
                for v in i.volumes.all():
                    iteration = 0
                    for s in v.snapshots.all():
                        if iteration is 0:
                            snapstart = s.start_time
                            snapdate = snapstart.strptime(str(snapstart)[:-13], "%Y-%m-%d %H:%M:%S")
                            difference = now - snapdate
                            if difference.days >= age:
                                instance_state = i.state["Name"]
                                print("Stopping {0}...".format(i.id))

                                i.stop()
                                i.wait_until_stopped()
                                if has_pending_snapshot(v):
                                    print("Skipping {0}, snapshot already in progress ".format(v.id))
                                    continue
                                else:
                                    print("   Creating snapshot of {0}".format(v.id))
                                    v.create_snapshot(Description="Created by Snapshotalyzer")
                                    if instance_state == 'stopped':
                                        break
                                    else:
                                        print("Starting {0}...".format(i.id))

                                        i.start()
                                        i.wait_until_running()
                            iteration = 1
                        else:
                            print("Skipping {0} due to the snapshot being less than {1} old.".format(v.id,difference))
                            break
            print("Job's done!")

        except botocore.exceptions.WaiterError as e:
            print("Could not complete snapshot(s) of {0}. ".format(i.id) + str(e))
            return
        except botocore.exceptions.ClientError as e:
            print("Could not complete snapshot(s) of {0}. ".format(i.id) + str(e))
            return


    else:
        print("Please specify a project name.")
    
    return

@instances.command('list')
@click.option('--project', default=None,
    help= "Only instances for project (tag Project:<name>)")
@click.pass_context
def list_instances(ctx, project):
    "List EC2 instances"

    ec2 = start_session(ctx.obj['PROFILE'],ctx.obj['REGION'])
    instances = filter_instances(ec2, project)

    for i in instances:
        tags = {t['Key']: t['Value'] for t in i.tags or []}
        print(', '.join((
            i.id,
            i.instance_type,
            i.placement['AvailabilityZone'],
            i.state['Name'],
            i.public_dns_name,
            tags.get('Project','<no project>')
            )))
    
    
    return

@instances.command('stop')
@click.option('--project', default=None,
    help='Only instances for project')
@click.option('--force', flag_value=True, default=False,
    help='Force instances to stop')
@click.option('--yes', is_flag=True, callback=abort_if_false,
    expose_value=False,
    prompt='Are you sure you want to stop?')
@click.option('--id', 'server_id', default=None,
    help="Specific instances")
@click.pass_context
def stop_instances(ctx, project, force, server_id):
    'Stop EC2 instances'

    ec2 = start_session(ctx.obj['PROFILE'],ctx.obj['REGION'])
    instances = filter_instances(ec2, project, server_id)

    if force or project or server_id:

            click.echo('Stopping instance(s)!')

            for i in instances:
                print("Stopping {0}...".format(i.id))
                try:
                    i.stop()
                except botocore.exceptions.ClientError as e:
                    print(" Could not stop {0}. ".format(i.id) + str(e))
                    continue

            return
    else:
        print('Please specify project name.')
    
    return

@instances.command('start')
@click.option('--project', default=None,
    help='Only instances for this project')
@click.option('--force', flag_value=True, default=False,
    help='Force instances to start')
@click.option('--yes', is_flag=True, callback=abort_if_false,
    expose_value=False,
    prompt='Are you sure you want to start?')
@click.option('--id', 'server_id', default=None,
    help="Specific instances")
@click.pass_context
def start_instances(ctx, project, force, server_id):
    'Start EC2 instances'

    ec2 = start_session(ctx.obj['PROFILE'],ctx.obj['REGION'])
    instances = filter_instances(ec2, project, server_id)

    if force or project or server_id:

        click.echo('Starting instance(s)!')

        for i in instances:
            print("Starting {0}...".format(i.id))
            try:
                i.start()
            except botocore.exceptions.ClientError as e:
                print(" Could not start {0}. ".format(i.id) + str(e))
                continue

        return

    else:
        print('Please specify project name.')
    
    return

@instances.command('reboot')
@click.option('--project', default=None,
    help='Only instances for this project')
@click.option('--force', flag_value=True, default=False,
    help='Force instances to reboot')
@click.option('--yes', is_flag=True, callback=abort_if_false,
    expose_value=False,
    prompt='Are you sure you want to reboot?')
@click.option('--id', 'server_id', default=None,
    help="Specific instances")
@click.pass_context
def reboot_instances(ctx, project, force, server_id):
    'Reboot EC2 Instances'

    ec2 = start_session(ctx.obj['PROFILE'],ctx.obj['REGION'])
    instances = filter_instances(ec2, project, server_id)

    if force or project or server_id:

        click.echo('Rebooting instance(s)!')

        for i in instances:
            print("Rebooting {0}...".format(i.id))
            try:
                i.reboot()
            except botocore.exceptions.ClientError as e:
                print(" Could not reboot {0}. ".format(i.id) + str(e))
                continue

        return

    else:
        print('Please specify project name.')
    
    return
    

if __name__ == '__main__':
    cli(obj={})
