import os
import yaml

from utils.cloud import ReferenceDataStorage

yaml_file = os.path.join(os.getcwd(), "settings.yaml")
def yaml_configuration():
    if os.path.exists(yaml_file):
        with open(yaml_file, "r") as f:
            doc = yaml.load(f)
            return doc

class Configuration(object):
    def __init__(self):
        self.reference = None
        self.copy_number_data = None
        self.scviz_embedding = None
        self.datapath = None
        self.jobpath = None
        self.referencepath = None
        self.build = None
        self.chemistry = "auto"
        self.qc_type = "tenx_filtered"
        self.low_counts_genes_threshold = 4
        self.stds = 6
        overrides = yaml_configuration()
        if overrides != None:
            for attr, value in overrides.items():
                setattr(self, attr, value)
        if self.reference is None and (self.build != None and self.reference != None):
            refobj = ReferenceDataStorage(self.build, self.referencepath)
            self.reference = refobj.download()
        if self.reference is not None:
            self.genes_gtf = os.path.join(self.reference, "genes/genes.gtf")

VM_REFERENCE = {
    'linux': {
        'publisher': 'Canonical',
        'offer': 'UbuntuServer',
        'sku': '16.04.0-LTS',
        'version': 'latest'
    },
}

LOCATION = 'canadaeast'
GROUP_NAME = 'nick'
VNET_NAME = 'scrnanet'
SUBNET_NAME = 'scrnasubnet'
NIC_NAME = 'scrnanic'
VM_NAME = 'scrna-test'
IP_ADDRESS_NAME='azure-sample-ip'
USERNAME = 'nickceglia@gmail.com'
PASSWORD = 'Aphahb_666'

def create_vm_parameters(nic_id, vm_reference):
    """Create the VM parameters structure.
    """
    return {
        'location': LOCATION,
        'os_profile': {
            'computer_name': VM_NAME,
            'admin_username': USERNAME,
            'admin_password': PASSWORD
        },
        'hardware_profile': {
            'vm_size': 'Standard_DS1_v2'
        },
        'storage_profile': {
            'image_reference': {
                'publisher': vm_reference['publisher'],
                'offer': vm_reference['offer'],
                'sku': vm_reference['sku'],
                'version': vm_reference['version']
            },
        },
        'network_profile': {
            'network_interfaces': [{
                'id': nic_id,
            }]
        },
    }
