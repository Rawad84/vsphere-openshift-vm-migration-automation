import ssl
import base64
import csv
from pyVim.connect import SmartConnect, Disconnect
from pyVmomi import vim
import requests
from kubernetes import client, config
from kubernetes.client import Configuration, ApiClient, CoreV1Api
from termcolor import colored
import sys
import socket



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

if user_input.lower() == "yes":
        
        # Use Kubernetes client to interact with the cluster
        api = client.CoreV1Api()
        list_namespace=[]
        # Example: List all namespaces in the cluster
        namespaces = api.list_namespace()
        for ns in namespaces.items:
            list_namespace.append(ns.metadata.name)
        

        # use to check if the namespace is already existed
        with open('vm_details.csv', "r") as file:
            reader = csv.reader(file)
            next(reader)  # Skip the first row
            data_rows = list(reader)
            

        if len(data_rows) > 0:    
            for row in data_rows:
                if len(row) > 0:
                                           
                        if row[0] in list_namespace:
                            colored_part = colored(row[0], 'green', attrs=['bold'])
                            print(colored_part , " namespace is exist")
                            custom_api = client.CustomObjectsApi()
                            try:
                                nad_list = custom_api.get_namespaced_custom_object(group="k8s.cni.cncf.io", version="v1", namespace=row[0], plural="network-attachment-definitions",name=row[2],)
                            
                            except Exception as e:
                                if "Not Found" in str(e):
                                    colored_nad = colored(row[2], 'red', attrs=['bold'])
                                    colored_namespace = colored(row[0], 'red', attrs=['bold'])
                                    print('The Network Attachment Definition', colored_nad , 'is not exist in the' , colored_namespace + 'namespace')
                                    print("Aborted.")
                                    sys.exit()
                                else:
                                    print("Error fetching the Network Attachment Definition:", e)
                                    print("Aborted.")
                                    sys.exit()

                            colored_nad = colored(row[2], 'green', attrs=['bold'])
                            colored_namespace = colored(row[0], 'green', attrs=['bold'])
                            print('The Network Attachment Definition', colored_nad , 'exists in the' , colored_namespace ,'namespace')
                            
                        else:
                            colored_part = colored(row[0], 'red', attrs=['bold'])
                            print(colored_part + " namespace is not exist")
                            print("Aborted.")
                            sys.exit()
                        
                else:
                    pass
            
else:
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
password = base64.b64decode(secret.data['password']).decode('utf-8')
user = base64.b64decode(secret.data['user']).decode('utf-8')
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
extracted_url = url[start_index + 2: end_index]

# Check vSphere server reachability
def check_vcenter_reachability(extracted_url):
    try:
        socket.create_connection((extracted_url, 443), timeout=5)
        return True
    except socket.gaierror:
        return False
    except socket.timeout:
        return False

# Verify vSphere server reachability before connecting
if not check_vcenter_reachability(extracted_url):
    print(f"Error: Unable to reach vSphere server at {extracted_url}. Please check the network connectivity.")
    sys.exit(1)
else:
    print(f"Success: vSphere server at {extracted_url} is reachable.")



# Disable SSL certificate verification
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Monkey patching the SSL adapter of the requests library
requests.packages.urllib3.disable_warnings()

if hasattr(ssl, '_create_unverified_context'):
    ssl._create_default_https_context = ssl._create_unverified_context

# Connect to vSphere without SSL verification
connection = SmartConnect(
    host=extracted_url,
    user=user,
    pwd=password,
    sslContext=ssl_context
)

# Find VMI based on VM name
def find_vmi_by_name(vm_name):
    content = connection.RetrieveContent()
    container = content.viewManager.CreateContainerView(content.rootFolder, [vim.VirtualMachine], True)

    for vm in container.view:
        if vm.name == vm_name:
            return vm

    return None

# Example usage: Find VMI for a specific VM name
with open('vm_details.csv', "r") as file:
    reader = csv.reader(file)
    next(reader)  # Skip the first row
    data_rows = list(reader)
    
    vm_details = []
    if len(data_rows) > 0:
        for row in data_rows:
             if len(row) > 0:
                vm_name = row[1]
                vmi = find_vmi_by_name(vm_name)

                if vmi:
                    if hasattr(vmi.guest, 'ipAddress'):
                        vm_ip = vmi.guest.ipAddress
                    
                    network_interfaces = vmi.config.hardware.device
                    
                    dev_key = vmi.network
                    for i in dev_key:
                        dv_portgroup = i._moId
  
                    
                    vm_state = vmi.summary.runtime.powerState
                    if vm_state == 'poweredOn':
                        print('The vm', row[1], 'state is', colored(vm_state, 'green', attrs=['bold']))
                    else:
                        print('The vm', row[1], 'state is', colored(vm_state, 'red', attrs=['bold']))
                    
                    datastore_ids = []
                    datastore_object = vmi.datastore
                    for i in datastore_object:
                        datastore_ids.append(i._moId)
                    
                    
                   
                    vm_details.append({'namespace': row[0],'VM_Name': row[1], 'Nad': row[2],'VM_ID': vmi._moId, 'IP Address': vm_ip, 'State': vmi.summary.runtime.powerState, 'dv_port': dv_portgroup, 'datastore': datastore_ids})

                else:
                    print("VMI not found for VM name:", vm_name)

# Disconnect from vSphere
Disconnect(connection)


csv_file = 'vm_list.csv'
header = ['namespace', 'VM_Name', 'Nad' , 'VM_ID', 'IP Address', 'State', 'dv_port', 'datastore' ]

with open(csv_file, 'w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=header)
    writer.writeheader()
    writer.writerows(vm_details)