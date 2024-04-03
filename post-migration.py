import requests
import urllib3
import os
from urllib.parse import urlparse
from vmware.vapi.vsphere.client import create_vsphere_client
from com.vmware.vapi.std_client import DynamicID
import re
import time
from kubernetes import client, config
from kubernetes.client import Configuration, ApiClient, CoreV1Api
from termcolor import colored
import sys
import socket
import base64
import datetime
from pyVim import connect
from pyVmomi import vim
import ssl
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim



# Enter the name of vm
vm_name = input('Please enter the name of vm: ')
current_date = datetime.datetime.now().strftime("%m%d%Y")
new_vm_name = f"{vm_name}-migrated-{current_date}"
destination_folder_name = 'Put here the name of Archive folder to move VM to'
# Check to see if the user has already logged into the OCP cluster

def is_user_logged_in():
    try:
         # Load the current user's Kubernetes configuration
         config.load_kube_config()

         # Create an API client
         api_client = client.ApiClient()

         # Check if the user is authenticated by making a request to the API server
         api_instance = client.CoreV1Api(api_client)
         api_instance.get_api_resources()
         return True

    except Exception:
         return False

if __name__ == "__main__":
    if is_user_logged_in():
        pass

    else:
        print("Pleas login into the OCP cluster first before run the script.")
        sys.exit()

# Load current user's OpenShift configuration and credentials
config.load_kube_config()

# Get the current context from the configuration
current_context = config.list_kube_config_contexts()[1]

# Get the cluster name from the current context
cluster_name = current_context['context']['cluster']

print(colored("The OCP cluster you are using is: ", 'black', attrs=['bold']) +''+ colored(cluster_name, 'red', attrs=['bold']))

user_input = input("Do you want to proceed? (Enter 'yes' to continue): ")

if user_input.lower() != "yes":
    print("Aborted.")
    sys.exit()


# Create a Kubernetes API client
api_client = client.CoreV1Api()

# find the name of the provider's secret
group = "forklift.konveyor.io"
version = "v1beta1"
plural = "providers"
api = client.CustomObjectsApi()

provider_list = api.list_cluster_custom_object(group=group, version=version, plural=plural)
for provider in provider_list["items"]:
    if "spec" in provider and "type" in provider["spec"] and provider["spec"]["type"] == "vsphere":
        provider_secret = provider["spec"]["secret"]["name"]

secret = api_client.read_namespaced_secret(provider_secret, "openshift-mtv")
VCENTER_PASS = base64.b64decode(secret.data['password']).decode('utf-8')
VCENTER_USER = base64.b64decode(secret.data['user']).decode('utf-8')
url = base64.b64decode(secret.data['url']).decode('utf-8')

# Find the index of the first "//" in the URL
start_index = url.find("//")
if start_index == -1:
    print("Invalid URL format")
    exit()

# Find the index of the first "/" after the "//"
end_index = url.find("/", start_index + 2)
if end_index == -1:
    print("Invalid URL format")
    exit()

# Extract the value between "//" and "/"
VCENTER_HOST = url[start_index + 2: end_index]


# Connect to vCenter Server

# Disable SSL certificate verification for the entire script
requests.packages.urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

session = requests.session()
session.verify = False
client = create_vsphere_client(server=VCENTER_HOST, username=VCENTER_USER, password=VCENTER_PASS, session=session)

def get_vm_by_name(vm_name):
    vms = client.vcenter.VM.list()
    #print(vms)
    for vm in vms:
        if vm.name == vm_name:
            print(vm.vm)
            return vm.vm
    print('VM is not exist, please make sure you provided the correct VM name')
    sys.exit()




def get_vm_nic(vm_name):
    vms = client.vcenter.VM.list()
    for vm in vms:
        if vm.name == vm_name:
            return vm.vm

def disconnect_nic(vm_name):
    vm = get_vm_nic(vm_name)
    list_nic = client.vcenter.vm.hardware.Ethernet.list(vm)
    if list_nic:
        for nic in list_nic:
            client.vcenter.vm.hardware.Ethernet.delete(vm, nic.nic)
            print( 'NIC was removed from the vm')
    else:
        print('There is no NIC attached to the VM')


disconnect_nic(vm_name)
time.sleep(1)

# Disable SSL certificate verification
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Monkey patching the SSL adapter of the requests library
requests.packages.urllib3.disable_warnings()

if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context
# Connect to vSphere without SSL verification
service_instance = SmartConnect(host=VCENTER_HOST,user=VCENTER_USER,pwd=VCENTER_PASS,sslContext=ssl_context)



# Move vm to the archive folder

def find_vm_in_datacenter(datacenter, vm_name):
    for vm_folder in datacenter.vmFolder.childEntity:
        if not hasattr(vm_folder, 'childEntity'):
            continue
        for vm in vm_folder.childEntity:
            if isinstance(vm, vim.VirtualMachine) and vm.name == vm_name:
                return vm
    return None
content = service_instance.RetrieveContent()
datacenter = content.rootFolder.childEntity[0]


# Find the VM by name
vm_to_move = find_vm_in_datacenter(datacenter, vm_name)

if vm_to_move:
    # Find the destination folder by name
    destination_folder = None
    for vm_folder in datacenter.vmFolder.childEntity:
         if vm_folder.name == destination_folder_name:
                    destination_folder = vm_folder
                    break
    if destination_folder:
    # Move the VM to the destination folder
        relocate_spec = vim.vm.RelocateSpec()
        relocate_spec.folder = destination_folder

        task = vm_to_move.Relocate(relocate_spec)

        print(' VM was moved to the destination folder')
    
    else:
        print(f"Destination folder '{destination_folder_name}' not found.")
else:
    print(f"VM '{vm_name}' not found in the datacenter.")



# Get the VM by name
def get_vm_by_name(vm_name):
    content = service_instance.RetrieveContent()
    for child in content.rootFolder.childEntity:
        if hasattr(child, 'vmFolder'):
            datacenter = child
            vm_folder = datacenter.vmFolder
            # Recursively traverse the folder structure to find VMs
            vm = find_vm_in_folder(vm_folder, vm_name)
            if vm:
                print(f"VM '{vm_name}' found.")
                return vm

    return None

def find_vm_in_folder(folder, vm_name):
    for entity in folder.childEntity:
        if isinstance(entity, vim.VirtualMachine):
            if entity.name == vm_name:
                return entity
        elif hasattr(entity, 'childEntity'):
                # If the entity has child entities, recursively search inside them
            vm = find_vm_in_folder(entity, vm_name)
            if vm:
                return vm
    return None

def rename_vm(vm_name, new_vm_name):
    vm = get_vm_by_name(vm_name)
    if vm:
        try:
            task = vm.Rename(new_vm_name)
            wait_for_task(task)
            print(f"VM '{vm.name}' has been renamed to '{new_vm_name}'.")
        except Exception as e:
            print(f"Failed to rename the VM. Error: {str(e)}")
    else:
        print(f"VM not found.")

def wait_for_task(task):
    while task.info.state not in [vim.TaskInfo.State.success, vim.TaskInfo.State.error]:
        time.sleep(1)
    if task.info.state == vim.TaskInfo.State.error:
        raise Exception(f"Task failed with error: {task.info.error}")

rename_vm(vm_name, new_vm_name)

# Disconnect from the vCenter Server
connect.Disconnect(service_instance)