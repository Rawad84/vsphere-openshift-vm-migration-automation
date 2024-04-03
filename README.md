# VMware vSphere VM Migration Automation
This repository contains automation scripts for managing VM migration tasks from VMware to Openshift. The migra The following instructions outline the execution process for migrating VMs using the provided Python scripts.

## Install Dependencies

1. To utlize the SDK used in post-migration.py script. Make sure you install it first following the instructions on the main page in [Repo](https://github.com/vmware/vsphere-automation-sdk-python).

2. Move inside the repository folder and execute the `install.py` script. This script checks for required Python modules and installs any missing ones
   
3. Create namespace and the network-attachment-definition for each VM need to be migrated to Openshift

## Code Execution

1. Prepare VM Details
The CSV file must adhere to a specified format and should be named "vm_details.csv," as demonstrated below:

   ```yaml
   namespace,Name,NAD

   11111,vm1,vlan11

   22222,vm2,vlan22

   33333,vm3,vlan33
   .
   .
   .
   ?????,???,???????
   ```

1. Stage VMs for Migration
Run the `vm_staging.py` script to perform pre-flight checks and gather VM-related data.


3. Generate Migration Plans
Execute the `create_plan.py` script to generate migration plans for each VM. This script generates migration plans and stores them in a JSON file (project_plans_map.json).


4. Initiate VM Migration
Execute the `migration.py` script to initiate VM migration based on the generated plans.This script triggers the VM migration process and updates the migration plans accordingly.

5.  Initiate Post migration  
After VM migration is concluded, execute the `post-migration.py` script to remove the  from the VM in VMware, rename it, and move it to archive folder in VMware for decomm later.

## Additional Information
Ensure proper configuration of Kubernetes (~/.kube/config) to access the OpenShift cluster.
For detailed execution logs and output, refer to individual script outputs and generated files.
Contributions and feedback are welcome! If you encounter any issues or have suggestions for improvements, feel free to open an issue or submit a pull request.
License
This project is licensed under the MIT License.
