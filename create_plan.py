from kubernetes import client, config
import csv
import json
import os
import ast

# Load the Kubernetes configuration (no need to change this part)
config.load_kube_config()

# Get the current namespace from the environment variable
mtv_namespace = os.environ.get('NAMESPACE')

# Create a Kubernetes API client
api_client = client.CoreV1Api()

# Create a CustomObjectsApi using the existing API client
custom_api = client.CustomObjectsApi(api_client.api_client)

# find the name of the provider

group = "forklift.konveyor.io"
version = "v1beta1"
plural = "providers"
api = client.CustomObjectsApi()

provider_list = api.list_cluster_custom_object(group=group, version=version, plural=plural)
for provider in provider_list["items"]:
    if "spec" in provider and "type" in provider["spec"] and provider["spec"]["type"] == "vsphere":
        if "metadata" in provider and "name" in provider["metadata"]:
            provider_type = provider["metadata"]["name"]


mtv_namespace = 'openshift-mtv'
provider_name = provider_type
project_plan_map = {}

# Specify the filename of the CSV file
filename = "vm_list.csv"

# Function to extract the list from the string in the CSV
def extract_list_from_csv(value):
    return eval(value)  # This assumes the list is in a valid Python literal representation

# Read data from CSV file
with open(filename, "r") as file:
    reader = csv.reader(file)
    next(reader)  # Skip the first row
    data_rows = list(reader)

    for row in data_rows:
        storage_mapping_name = row[1] + "-storage"
        network_mapping_name = row[1] + "-network"
        migration_name = row[2] + "-migration"
        
        # Check if storage mapping already exists
        existing_storage_mapping = None
        try:
            existing_storage_mapping = custom_api.get_namespaced_custom_object(
                group="forklift.konveyor.io",
                version="v1beta1",
                namespace=mtv_namespace,
                plural="storagemaps",
                name=storage_mapping_name,
            )
        except client.ApiException as e:
            if e.status != 404:
                raise
        
        # Check if network mapping already exists
        existing_network_mapping = None
        try:
            existing_network_mapping = custom_api.get_namespaced_custom_object(
                group="forklift.konveyor.io",
                version="v1beta1",
                namespace=mtv_namespace,
                plural="networkmaps",
                name=network_mapping_name,
            )
        except client.ApiException as e:
            if e.status != 404:
                raise
        
        if existing_storage_mapping:
            print(f'Skipping VM {row[1]}: Storage mapping already exists')
            continue  # Skip to the next VM

        if existing_network_mapping:
            print(f'Skipping VM {row[1]}: Network mapping already exists')
            continue  # Skip to the next VM

        storage_plan_mapping = []
        # Create storage mapping
        print(f'creating storage mapping for {row[1]}')
        datastore_list = ast.literal_eval(row[7])
        for sd_id in datastore_list:
            
            storage_entry = {
            "destination": {
                "storageClass": "ocs-storagecluster-ceph-rbd-virtualization"
            },
            "source": {
                "id": sd_id
            }
        }
            storage_plan_mapping.append(storage_entry)
        
        
        storage_object = {
        "apiVersion": "forklift.konveyor.io/v1beta1",
        "kind": "StorageMap",
        "metadata": {
            "name": row[1]+"-storage",
            "namespace": mtv_namespace
        },
        "spec": {
            "map":storage_plan_mapping,
            "provider": {
                "destination": {
                    "name": "host",
                    "namespace": mtv_namespace
                },
                "source": {
                    "name": provider_name,
                    "namespace": mtv_namespace
                }
            }
        }
    }
        
        
        custom_api.create_namespaced_custom_object(
        group="forklift.konveyor.io",
        version="v1beta1",
        namespace=mtv_namespace,
        plural="storagemaps",
        body=storage_object
    )

        print(f'creating network mapping for {row[1]}')
        # Create network mapping
        network_plan_mapping = []
        network_entry = {
                "destination": {
                    "name": row[2],
                    'namespace': row[0],
                    'type': 'multus'

                },
                "source": {
                    "id": row[6]
                }
        }
        network_plan_mapping.append(network_entry)

        
        network_object = {
            "apiVersion": "forklift.konveyor.io/v1beta1",
            "kind": "NetworkMap",
            "metadata": {
                "name": row[1]+"-network",
                "namespace": mtv_namespace
            },
            "spec": {
                "map": network_plan_mapping,
                "provider": {
                    "destination": {
                        "name": "host",
                        "namespace": mtv_namespace
                    },
                    "source": {
                        "name": provider_name,
                        "namespace": mtv_namespace
                    }
                }
            }
        }
        custom_api.create_namespaced_custom_object(
            group="forklift.konveyor.io",
            version="v1beta1",
            namespace=mtv_namespace,
            plural="networkmaps",
            body=network_object
)

    
        project_name = row[0]
        vm_plan_list = []
        #create VM list
        vm_entry = {
                "hooks": [],
                "id": row[3]
        }
        vm_plan_list.append(vm_entry)

        print(f'creating migration plan for {row[1]}')
        #create Plan
        plan_name = row[1]+"-plan"
        plan_object = {
            "apiVersion": "forklift.konveyor.io/v1beta1",
            "kind": "Plan",
            "metadata": {
                "name": plan_name,
                "namespace": mtv_namespace
            },
            "spec": {
                "archived": False,
                "description": "",
                "map": {
                    "network": {
                        "name": row[1]+"-network",
                        "namespace": mtv_namespace
                    },
                    "storage": {
                        "name": row[1]+"-storage",
                        "namespace": mtv_namespace
                    }
                },
                "provider": {
                    "destination": {
                        "name": "host",
                        "namespace": mtv_namespace
                    },
                    "source": {
                        "name": provider_name,
                        "namespace": mtv_namespace
                    }
                },
                "targetNamespace": project_name,
                "TransferNetwork": {
                    "name": row[2], 
                    "namespace": project_name
                },
                "vms": vm_plan_list,
                "warm": False
            }
            
        }
        custom_api.create_namespaced_custom_object(
        group="forklift.konveyor.io",
        version="v1beta1",
        namespace=mtv_namespace,
        plural="plans",
        body=plan_object
    )
        
        project_plan_map[row[3]+"-migration"] = plan_name
        
#create JSON file with project and paln names mapping
project_plan_json = json.dumps({str(k): v for k, v in project_plan_map.items()})

with open('project_plans_map.json', 'w') as f:
    f.write(project_plan_json)
    f.close()








