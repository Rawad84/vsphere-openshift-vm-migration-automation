from kubernetes import client, config
import json
import os
from datetime import datetime
import subprocess

# Load Kubernetes configuration
config.load_kube_config()

# Define the folder name
folder_name = "migrationPlan"

# Create the folder if it doesn't exist
if not os.path.exists(folder_name):
    os.makedirs(folder_name)

# Load the project plans map from the JSON file
with open('project_plans_map.json') as f:
    plans_list = json.load(f)

# Check if there are any entries in the plans_list
if not plans_list:
    print("No migration plans found in the JSON file. Exiting.")
    exit()

# Get the current date in the format YYYY-MM-DD
current_date = datetime.now().strftime("%Y-%m-%d")

# Create the filename with the current date
filename = f"{folder_name}/project_plans_map_{current_date}.json"

# Check if the file already exists
if not os.path.exists(filename):
    # Create JSON file with project and plan names mapping
    project_plan_json = json.dumps({str(k): v for k, v in plans_list.items()})
    
    # Write the JSON data to the file with the current date
    with open(filename, 'w') as f:
        f.write(project_plan_json)

    print(f"JSON file '{filename}' created and saved.")
else:
    print(f"JSON file '{filename}' already exists.")

# Define the command
command = ["oc", "get", "migration"]

# Run the command
try:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    # Count the number of migration plans
    lines = result.stdout.strip().split('\n')
    num_migration_plans = len(lines) - 1  # Subtract 1 to exclude the header
    if num_migration_plans < 10:
        # Get the first subset of VMs from the JSON data
        VM_migrated = list(plans_list.items())[:(9 - num_migration_plans)]

        # Create a Kubernetes API client
        api_cr_client = client.ApiClient()
        custom_api = client.CustomObjectsApi(api_cr_client)

        mtv_namespace = 'openshift-mtv'

        for migration, plan_name in VM_migrated:
            # Create migration
            migration_object = {
                "apiVersion": "forklift.konveyor.io/v1beta1",
                "kind": "Migration",
                "metadata": {
                    "name": migration,
                    "namespace": mtv_namespace
                },
                "spec": {
                    "plan": {
                        "name": plan_name,
                        "namespace": mtv_namespace
                    }
                }
            }

            print(f"Creating migration for {migration} with plan {plan_name}")

            custom_api.create_namespaced_custom_object(
                group="forklift.konveyor.io",
                version="v1beta1",
                namespace=mtv_namespace,
                plural="migrations",
                body=migration_object
            )

        # Remove the migrated VMs entries from the JSON data
        for migration, _ in VM_migrated:
            plans_list.pop(migration)

        # Write the modified JSON data back to the file
        with open('project_plans_map.json', 'w') as f:
            json.dump(plans_list, f)

        print(f'The migration of VMs is in progress, and their respective entries have been removed from the JSON file.')
    else:
        print("The current migration process is at its maximum capacity for VMs.")
        exit()

except subprocess.CalledProcessError as e:
    print("Command failed with error:")
    print(e.std)