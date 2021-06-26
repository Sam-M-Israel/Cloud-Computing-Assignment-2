REGION=us-east-2
RUN_ID=$(date +'%sN')
KEY_NAME="cc-sam-omer-$RUN_ID"
KEY_PEM="$KEY_NAME.pem"

echo "Create key pair $KEY_PEM to connect to instances and save locally"
aws ec2 create-key-pair --key-name $KEY_NAME | jq -r ".KeyMaterial" > $KEY_PEM

# secure the key pair
chmod 400 $KEY_PEM

# shellcheck disable=SC2006
SEC_GRP="cloud-comp-2-sam-omer-$RUN_ID"

echo "setup firewall $SEC_GRP"
aws ec2 create-security-group   \
    --group-name $SEC_GRP       \
    --description "Access my instances"

# figure out my ip
MY_IP=$(curl ipinfo.io/ip)
echo "My IP: $MY_IP"

# Getting subnets for the ELB and VPC ID
echo "Getting the 3 Subnets and VPC ID's"
SUBNET_ID_1=$(aws ec2 describe-subnets --filters Name=default-for-az,Values=true | jq -r .Subnets[0] | jq -r .SubnetId)
SUBNET_ID_2=$(aws ec2 describe-subnets --filters Name=default-for-az,Values=true | jq -r .Subnets[1] | jq -r .SubnetId)
SUBNET_ID_3=$(aws ec2 describe-subnets --filters Name=default-for-az,Values=true | jq -r .Subnets[2] | jq -r .SubnetId)
VPC_ID=$(aws ec2 describe-subnets --filters Name=default-for-az,Values=true | jq -r .Subnets[0] | jq -r .VpcId)
VPC_CIDRBLOCK=$(aws ec2 describe-vpcs --filters Name=vpc-id,Values=$VPC_ID | jq -r .Vpcs[0].CidrBlock)
echo "Subnet ID 1: $SUBNET_ID_1"
echo "Subnet ID 2: $SUBNET_ID_2"
echo "Subnet ID 3: $SUBNET_ID_3"
echo "VPC ID: $VPC_ID"
echo "VPC cidr block: $VPC_CIDRBLOCK"

# Creating a cloud formation stack
echo "Creating cloud formation stack "
STACK_NAME="sam-omer-stack"
STACK_RESULT=$(aws cloudformation create-stack --stack-name $STACK_NAME --template-body file://cloudFormationEc2.json --capabilities CAPABILITY_IAM \
          --parameters ParameterKey=InstanceType,ParameterValue=t2.micro \
          ParameterKey=KeyName,ParameterValue=$KEY_NAME \
	        ParameterKey=SSHLocation,ParameterValue=$MY_IP/32 \
          ParameterKey=SubnetID1,ParameterValue=$SUBNET_ID_1 \
          ParameterKey=SubnetID2,ParameterValue=$SUBNET_ID_2 \
          ParameterKey=SubnetID3,ParameterValue=$SUBNET_ID_3 \
          ParameterKey=VPCId,ParameterValue=$VPC_ID \
          ParameterKey=VPCcidr,ParameterValue=$VPC_CIDRBLOCK)

echo "Waiting for stack: $STACK_NAME to be created..."
STACK_ID=$(echo $STACK_RESULT | jq -r '.StackId')
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME

# Getting the wanted stack
STACK=$(aws cloudformation --region $REGION describe-stacks --stack-name $STACK_NAME | jq -r .Stacks[0])

# Printing the stack outputs
echo "Printing $STACK_NAME outputs..."
OUTPUTS=$(echo $STACK | jq -r .Outputs)
echo $OUTPUTS

echo "Getting EC2 instance IP's from stack: $STACK_NAME"
Ec2_1_IP=$(aws cloudformation --region $REGION describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='EC2Node1IP'].OutputValue" --output text)
Ec2_1_ID=$(aws cloudformation --region $REGION describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='EC2Node1ID'].OutputValue" --output text)

Ec2_2_IP=$(aws cloudformation --region $REGION describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='EC2Node2IP'].OutputValue" --output text)
Ec2_2_ID=$(aws cloudformation --region $REGION describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='EC2Node2ID'].OutputValue" --output text)

Ec2_3_IP=$(aws cloudformation --region $REGION describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='EC2Node3IP'].OutputValue" --output text)
Ec2_3_ID=$(aws cloudformation --region $REGION describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='EC2Node3ID'].OutputValue" --output text)
STACK_TGROUP=$(aws cloudformation --region $REGION describe-stacks --stack-name $STACK_NAME --query "Stacks[0].Outputs[?OutputKey=='TargetGroup'].OutputValue" --output text)

echo "New instance at $Ec2_1_IP with subnet: $SUBNET_ID_1"
echo "New instance at $Ec2_2_IP with subnet: $SUBNET_ID_2"
echo "New instance at $Ec2_3_IP with subnet: $SUBNET_ID_3"
echo "Waiting for instances to register as healthy..."
aws ec2 wait instance-status-ok --instance-ids $Ec2_1_ID
echo "$Ec2_1_ID registered as healthy"
aws ec2 wait instance-status-ok --instance-ids $Ec2_2_ID
echo "$Ec2_2_ID registered as healthy"
aws ec2 wait instance-status-ok --instance-ids $Ec2_3_ID
echo "$Ec2_3_ID registered as healthy"

# Target Health check
echo "Checking $STACK_TGROUP health"
T_HEALTH_CHECK=$(aws elbv2 describe-target-health --target-group-arn $STACK_TGROUP)
echo "$T_HEALTH_CHECK"

ELB_NAME="SamOmerELB"
echo "Getting DNS Name for ELB: $ELB_NAME"
DNS_ADD=$(aws elbv2 describe-load-balancers --names $ELB_NAME | jq -r .LoadBalancers[0].DNSName)
echo "$DNS_ADD"

#echo "setup rule allowing SSH access to $MY_IP only"
#aws ec2 authorize-security-group-ingress        \
#    --group-name $SEC_GRP --port 22 --protocol tcp \
#    --cidr $MY_IP/32
#
#echo "setup rule allowing HTTP (port 5000) access to $MY_IP only"
#aws ec2 authorize-security-group-ingress        \
#    --group-name $SEC_GRP --port 5000 --protocol tcp \
#    --cidr $MY_IP/32
#
#UBUNTU_20_04_AMI="ami-08962a4068733a2b6"
#
#echo "Creating Ubuntu 20.04 instance..."
#RUN_INSTANCES=$(aws ec2 run-instances   \
#    --image-id $UBUNTU_20_04_AMI        \
#    --instance-type t2.micro            \
#    --key-name $KEY_NAME                \
#    --security-groups $SEC_GRP)
#
#INSTANCE_ID=$(echo $RUN_INSTANCES | jq -r '.Instances[0].InstanceId')
#
#echo "Waiting for instance creation..."
#aws ec2 wait instance-running --instance-ids $INSTANCE_ID
#
#PUBLIC_IP=$(aws ec2 describe-instances  --instance-ids $INSTANCE_ID |
#    jq -r '.Reservations[0].Instances[0].PublicIpAddress'
#)
#
#echo "New instance $INSTANCE_ID @ $PUBLIC_IP"
#echo "deploying code to production"
#scp -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=60" launch_script.sh ubuntu@$PUBLIC_IP:/home/ubuntu/
#
#echo "setup production environment"
#ssh -i $KEY_PEM -o "StrictHostKeyChecking=no" -o "ConnectionAttempts=10" ubuntu@$PUBLIC_IP <<EOF
#  sh -e launch_script.sh
#EOF
#
#echo "test that it all worked"
#curl  --retry-connrefused --retry 10 --retry-delay 1  http://$PUBLIC_IP:5000

